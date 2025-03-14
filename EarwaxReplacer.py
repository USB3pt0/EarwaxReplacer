# Import important libraries
import os
import gc
import glob
import json
import numpy as np
import torch
import soundfile as sf
import pyrubberband as pyrb
import winreg
from scipy.io import wavfile
from scipy.signal import stft, lfilter, butter
from pydub import AudioSegment
from TTS.api import TTS
import sys
import re
import subprocess
import torch.serialization
from TTS.tts.configs.xtts_config import XttsAudioConfig, XttsConfig, XttsArgs
from TTS.config.shared_configs import BaseDatasetConfig
import urllib.request
import zipfile
import shutil

# Rubberband functions to detect and install if not present
# This is a dependency for pydub to convert audio files to wav with effects


def is_rubberband_installed():
    try:
        subprocess.check_call(
            ["rubberband", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_rubberband():
    url = "https://breakfastquay.com/files/releases/rubberband-1.9.2-gpl-executable-windows.zip"
    download_path = os.path.join(os.getcwd(), "rubberband.zip")
    extract_path = os.path.join(os.getcwd(), "rubberband")

    # Download the zip file
    print("Downloading rubberband-cli...")
    urllib.request.urlretrieve(url, download_path)

    # Extract the zip file
    print("Extracting rubberband-cli...")
    with zipfile.ZipFile(download_path, "r") as zip_ref:
        zip_ref.extractall(extract_path)

    # Move the executable to a directory in PATH
    rubberband_executable = os.path.join(
        extract_path, "rubberband-1.9.2-gpl-executable-windows", "rubberband.exe"
    )
    destination_path = os.path.join(os.getcwd(), "rubberband.exe")
    shutil.move(rubberband_executable, destination_path)

    # Clean up
    os.remove(download_path)
    shutil.rmtree(extract_path)

    # Verify the installation
    try:
        subprocess.check_call(
            ["rubberband", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("rubberband-cli is verified and working.")
    except subprocess.CalledProcessError as e:
        print(f"Verification failed: {e}")
        raise


def is_libsndfile_installed():
    if os.path.exists("sndfile.dll"):
        return True
    return False


def install_libsndfile():
    url = "https://github.com/libsndfile/libsndfile/releases/download/1.2.2/libsndfile-1.2.2-win64.zip"
    download_path = os.path.join(os.getcwd(), "libsndfile.zip")
    extract_path = os.path.join(os.getcwd(), "libsndfile")

    # Download the zip file
    print("Downloading libsndfile...")
    urllib.request.urlretrieve(url, download_path)

    # Extract the zip file
    print("Extracting libsndfile...")
    with zipfile.ZipFile(download_path, "r") as zip_ref:
        zip_ref.extractall(extract_path)

    # Move the DLL to a directory in PATH
    sndfile_dll = os.path.join(
        extract_path, "libsndfile-1.2.2-win64", "bin", "sndfile.dll"
    )
    destination_path = os.path.join(os.getcwd(), "sndfile.dll")
    shutil.move(sndfile_dll, destination_path)

    # Clean up
    os.remove(download_path)
    shutil.rmtree(extract_path)


# ----- File and Path Management Functions -----


def get_steam_libraries():
    libraries = []
    try:
        # Open the Steam registry key
        steam_key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"
        )
        steam_path, _ = winreg.QueryValueEx(steam_key, "InstallPath")
        libraries.append(os.path.join(steam_path, "steamapps"))
        winreg.CloseKey(steam_key)

        # Check for additional Steam libraries
        library_folders_file = os.path.join(
            steam_path, "steamapps", "libraryfolders.vdf"
        )
        if os.path.exists(library_folders_file):
            with open(library_folders_file, "r") as f:
                for line in f:
                    if "path" in line:
                        path = line.split('"')[3].replace("\\\\", "\\")
                        libraries.append(os.path.join(path, "steamapps"))
    except Exception as e:
        print(f"Error finding Steam libraries: {e}")
    return libraries


def find_jackbox_party_pack_2(libraries):
    for library in libraries:
        appmanifest_path = os.path.join(library, "appmanifest_397460.acf")
        if os.path.exists(appmanifest_path):
            with open(appmanifest_path, "r") as f:
                for line in f:
                    if '"installdir"' in line:
                        install_dir = line.split('"')[3]
                        game_path = os.path.join(library, "common", install_dir)
                        return game_path
    return None


def locate_jackbox_path():
    steam_libraries = get_steam_libraries()
    jackbox_path = find_jackbox_party_pack_2(steam_libraries)
    global located_automatically
    located_automatically = True

    if jackbox_path:
        print(
            f'The Jackbox Party Pack 2 is installed at: \033[94m"{jackbox_path}"\033[0m'
        )
    else:
        print("The Jackbox Party Pack 2 installation path could not be found.")
        prompt = input(
            "Please enter the installation path for The Jackbox Party Pack 2: "
        )
        jackbox_path = prompt.strip()
        located_automatically = False

    earwax_content = os.path.join(jackbox_path, "games", "Earwax", "content")
    if os.path.exists(earwax_content):
        print(f'Earwax content path found at: \033[94m"{earwax_content}"\033[0m')
    else:
        print("The Earwax Content path could not be found. Exiting.")
        sys.exit()

    return jackbox_path, earwax_content


def create_backups(earwax_content):
    backup_files = ["EarwaxAudio.jet", "EarwaxPrompts.jet"]
    for backup_file in backup_files:
        original_file = os.path.join(earwax_content, backup_file)
        backup_file_path = os.path.join(earwax_content, backup_file + ".bak")
        if os.path.exists(original_file) and not os.path.exists(backup_file_path):
            print(f'Creating backup for \033[94m"{backup_file}"\033[0m')
            with open(original_file, "rb") as f_src:
                with open(backup_file_path, "wb") as f_dst:
                    f_dst.write(f_src.read())


def copy_prompt_files(earwax_content, local_source_voice_path):
    earwax_prompts_path = os.path.join(earwax_content, "EarwaxPrompts")

    if not os.path.exists(local_source_voice_path):
        os.mkdir(local_source_voice_path)

    total_files_copied = 0
    for filename in os.listdir(earwax_prompts_path):
        if filename.endswith(".ogg") and re.match(r"^\d+_[a-zA-Z0-9]+", filename):
            local_file_path = os.path.join(local_source_voice_path, filename)
            wav_filename = os.path.splitext(filename)[0] + ".wav"
            local_wav_path = os.path.join(local_source_voice_path, wav_filename)
            if not os.path.exists(local_file_path) and not os.path.exists(
                local_wav_path
            ):
                print(" " * 150, end="\r")  # Clear the line
                print(
                    f'Copying \033[94m"{filename}"\033[0m to local source_voice folder',
                    end="\r",
                )
                source_file_path = os.path.join(earwax_prompts_path, filename)
                with open(source_file_path, "rb") as src_file:
                    with open(local_file_path, "wb") as dst_file:
                        dst_file.write(src_file.read())
                total_files_copied += 1
                print(" " * 150, end="\r")  # Clear the line
    print("Finished Copying Source Voice Files")
    print(
        f"Total Prompt files copied for source voice: \033[94m{total_files_copied}\033[0m"
    )


# ----- Audio Processing Functions -----


def butter_params(low_freq, high_freq, fs, order=5):
    nyq = 0.5 * fs
    low = low_freq / nyq
    high = high_freq / nyq
    b, a = butter(order, [low, high], btype="band")
    return b, a


def butter_bandpass_filter(data, low_freq, high_freq, fs, order=5):
    b, a = butter_params(low_freq, high_freq, fs, order=order)
    y = lfilter(b, a, data)
    return y


def speedUpAudio(filename, rate):
    y, sr = sf.read(filename)
    y_stretch = pyrb.time_stretch(y, sr, rate)
    y_shift = pyrb.pitch_shift(y, sr, rate)
    return y_stretch, sr


def set_echo(fs, data, delay):
    # Applies an echo that is 0...<input audio duration in seconds> seconds from the beginning
    output_audio = np.zeros(len(data))
    output_delay = delay * fs

    for count, e in enumerate(data):
        output_audio[count] = (e * 0.5) + (data[count - int(output_delay)] * 0.5)

    return output_audio


def getChannelScaled(ChannelData, fs):
    # Compute the Short-Time Fourier Transform (STFT)
    frequencies, times, Zxx = stft(ChannelData, fs=fs, nperseg=64)

    # Convert to magnitude spectrum
    magnitude_spectra = np.abs(Zxx)

    # Downsample to 32 frequency values
    num_bins = 32
    current_bins = magnitude_spectra.shape[0]

    # Trim the magnitude_spectra to a size that is divisible by num_bins
    trimmed_bins = (current_bins // num_bins) * num_bins
    trimmed_magnitude_spectra = magnitude_spectra[:trimmed_bins, :]

    # Calculate bin size after trimming
    bin_size = trimmed_bins // num_bins

    # Average the magnitude spectra in bins
    reduced_magnitude_spectra = np.mean(
        trimmed_magnitude_spectra.reshape((num_bins, bin_size, -1)), axis=1
    )

    max_output_val = 100
    # Scale the reduced magnitude spectra to 0-max_val range
    min_val = np.min(reduced_magnitude_spectra)
    max_val = np.max(reduced_magnitude_spectra)
    scaled_reduced_magnitude_spectra = (
        max_output_val * (reduced_magnitude_spectra - min_val) / (max_val - min_val)
    )

    # Round the scaled values to the nearest integer and convert to integer type
    integer_scaled_reduced_magnitude_spectra = np.round(
        scaled_reduced_magnitude_spectra
    ).astype(int)

    return integer_scaled_reduced_magnitude_spectra


def convert_audio_files(sounds_dir):
    # Find any supported non-ogg files and convert them to ogg
    extension_list = ("*.mp3", "*.wav")
    os.chdir(sounds_dir)

    # Create directory to move original audio files
    if not os.path.exists("Original Audio Files"):
        os.mkdir("Original Audio Files")

    for extension in extension_list:
        for audio in glob.glob(extension):
            print(" " * 150, end="\r")  # Clear the line
            print(
                f'Converting \033[94m"{os.path.basename(audio)}"\033[0m to ogg',
                end="\r",
            )
            # Use pydub to create the ogg file
            audio_filename = os.path.splitext(os.path.basename(audio))[0] + ".ogg"
            AudioSegment.from_file(audio).export(
                audio_filename, format="ogg", bitrate="64k"
            )
            # Move the original audio file to subdir, overwrite if exists
            destination_path = "Original Audio Files/" + os.path.basename(audio)
            if os.path.exists(destination_path):
                os.remove(destination_path)
            os.rename(os.path.basename(audio), destination_path)
            print(" " * 150, end="\r")  # Clear the line
    print(f'Finished Converting Audio Files in \033[94m"{sounds_dir}"\033[0m')


def generate_spectrum_files(sounds_dir, base_dir):
    print("Generating Spectrum files...")
    # Initialize files array
    files = []

    # Step through the directory and index every name in an array
    for dirname, dirnames, filenames in os.walk(sounds_dir):
        # Strip the .ogg from every .ogg file and shove it in the array
        for filename in filenames:
            if filename.endswith(".ogg"):
                filename = filename[:-4]
                files.append(filename)

    # Create spectrum folder if not present
    spectrum_dir = os.path.join(base_dir, "Spectrum")
    if not os.path.exists(spectrum_dir):
        os.mkdir(spectrum_dir)

    # Generate a spectrum file for each audio file
    for file in files:
        AudioName = file  # Audio File
        AudioWavFile = os.path.join(sounds_dir, AudioName + ".wav")
        AudioOggFile = os.path.join(sounds_dir, AudioName + ".ogg")
        AudioSpectrumFile = os.path.join(spectrum_dir, AudioName + ".jet")

        if os.path.exists(AudioSpectrumFile):
            print(
                f'Spectrum File Already Exists for \033[94m"{os.path.basename(file)}"\033[0m',
                end="\r",
            )
            print(" " * 150, end="\r")  # Clear the line
            continue

        print(
            f'Generating Spectrum File for \033[94m"{os.path.basename(file)}"\033[0m',
            end="\r",
        )

        # Convert ogg to wav for analysis
        try:
            audio = AudioSegment.from_file(AudioOggFile)
            audio = audio.set_frame_rate(1376)
            audio.export(AudioWavFile, format="wav")

            # Analyze WAV file
            fs, Audiodata = wavfile.read(AudioWavFile)

            # Do this spectrum analysis for each Channel
            if len(Audiodata.shape) > 1:
                # Stereo
                AudiodataLeft = Audiodata[:, 0]
                AudiodataRight = Audiodata[:, 1]
            else:
                # Copy Channel Data for Mono files
                AudiodataLeft = Audiodata
                AudiodataRight = Audiodata

            LeftData = getChannelScaled(AudiodataLeft, fs)
            RightData = getChannelScaled(AudiodataRight, fs)

            # Create output json for the Spectrum .jet file
            output_data = {"Refresh": 23, "Frequencies": [], "Peak": 100}
            for i in range(LeftData.shape[1]):
                thisRow = {"left": [], "right": []}
                for j in range(len(LeftData)):
                    # Convert the arrays to lists of native Python integers
                    LeftData_list = LeftData.tolist()
                    RightData_list = RightData.tolist()
                    thisRow["left"].append(LeftData_list[j][i])
                    thisRow["right"].append(RightData_list[j][i])
                output_data["Frequencies"].append(thisRow)

            # Write the Spectrum file
            with open(AudioSpectrumFile, "w") as f:
                json.dump(output_data, f)

        except Exception as e:
            print(f"Error processing {file}: {e}")

        # Cleanup!
        try:
            os.remove(AudioWavFile)
        except Exception as e:
            print(f"Error removing temp file: {e}")
        print(" " * 150, end="\r")  # Clear the line
    print("Finished Generating Spectrum Files")
    print(f"Total spectrum files: \033[94m{len(files)}\033[0m")
    return files


# ----- TTS Functions -----


def prepare_source_voice(base_dir):
    source_voice = []

    # See if there are files in source_voice
    source_voice_dir = os.path.join(base_dir, "source_voice")
    if os.path.exists(source_voice_dir):
        # Convert any ogg or mp3 to wav
        extension_list = ("*.ogg", "*.mp3")
        os.chdir(source_voice_dir)

        # Create directory to move original audio files
        if not os.path.exists("Original Audio Files"):
            os.mkdir("Original Audio Files")

        for extension in extension_list:
            for audio in glob.glob(extension):
                print(" " * 150, end="\r")  # Clear the line
                print(
                    f'Converting \033[94m"{os.path.basename(audio)}"\033[0m to wav',
                    end="\r",
                )
                # Use pydub to create the wav file
                audio_filename = os.path.splitext(os.path.basename(audio))[0] + ".wav"
                AudioSegment.from_file(audio).export(audio_filename, format="wav")

                # Move the original audio file to subdir
                destination_path = "Original Audio Files/" + os.path.basename(audio)
                if os.path.exists(destination_path):
                    os.remove(destination_path)
                os.rename(os.path.basename(audio), destination_path)
                print(" " * 150, end="\r")  # Clear the line

        print('Finished Converting Audio Files in \033[94m"source_voice"\033[0m')
        # Save list of .wav files to use for speech cloning
        for audio in glob.glob("*.wav"):
            source_voice.append(os.path.join("source_voice", audio))

        os.chdir(base_dir)

    return source_voice


def generate_prompts(base_dir, source_voice):
    # Check if there is a prompts.txt file present and we have a source voice
    prompts_file = os.path.join(base_dir, "prompts.txt")
    if not os.path.exists(prompts_file) or not source_voice:
        return None

    print("Generating prompts...")
    # Create initial object structure for prompt json
    output_data = {"content": []}

    # Create output folder for prompt audio
    prompts_output_dir = os.path.join(base_dir, "EarwaxPrompts")
    if not os.path.exists(prompts_output_dir):
        os.mkdir(prompts_output_dir)

    # Init TTS Variables
    tts = None
    # Get device
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # Add XttsConfig,XttsAudioConfig,BaseDatasetConfig,XttsArgs to safe globals
    torch.serialization.add_safe_globals([XttsConfig])
    torch.serialization.add_safe_globals([XttsAudioConfig])
    torch.serialization.add_safe_globals([BaseDatasetConfig])
    torch.serialization.add_safe_globals([XttsArgs])

    print(f"Using {device} for TTS processing")

    # Process each non-empty line of the file into a prompt
    promptID = 0
    with open(prompts_file, "r") as a_file:
        for line in a_file:
            stripped_line = line.strip()
            if stripped_line != "":
                print(" " * 150, end="\r")  # Clear the line
                print(
                    f'Generating Prompt: \033[94m"{stripped_line}"\033[0m id: \033[94m"{promptID}"\033[0m',
                    end="\r",
                )
                # Generate a prompt ID
                thisPromptID = 10000 + promptID

                # Generate prompt audio
                outputTTSFile = os.path.join(prompts_output_dir, f"{thisPromptID}.wav")
                outputOGGFile = os.path.join(prompts_output_dir, f"{thisPromptID}.ogg")

                if not os.path.exists(outputOGGFile):
                    if tts is None:
                        # Init TTS Engine
                        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(
                            device
                        )

                    ttsString = (
                        stripped_line.replace("<ANY>", "this player")
                        .replace("<i>", "")
                        .replace("</i>", "")
                    )
                    tts.tts_to_file(
                        text=ttsString,
                        file_path=outputTTSFile,
                        speaker_wav=source_voice,
                        language="en",
                    )

                    # Add distortions to make the voice sound like M.O.T.H.E.R.
                    fs, audio = wavfile.read(outputTTSFile)
                    low_freq = 200.0
                    high_freq = 5000.0
                    filtered_signal = butter_bandpass_filter(
                        audio, low_freq, high_freq, fs, order=6
                    )

                    filtered_signal = set_echo(fs, audio, 0.01)

                    outputMODFile = outputTTSFile.split(".wav")[0] + "_modded.wav"
                    wavfile.write(
                        outputMODFile, fs, np.array(filtered_signal, dtype=np.int16)
                    )

                    sped_up_signal, sr = speedUpAudio(outputMODFile, 1.125)
                    sf.write(outputMODFile, sped_up_signal, sr, format="wav")

                    # Convert the final wav to ogg for Jackbox
                    final_audio = AudioSegment.from_file(outputMODFile)
                    # Increase volume to match original game audio level
                    final_audio = final_audio + 6
                    final_audio.export(outputOGGFile, format="ogg", bitrate="64k")

                    # Delete the intermediate files
                    os.unlink(outputTTSFile)
                    os.unlink(outputMODFile)

                # Generate prompt object data
                promptData = {
                    "id": thisPromptID,
                    "x": False,
                    "PromptAudio": thisPromptID,
                    "name": stripped_line,
                }
                output_data["content"].append(promptData)

                promptID += 1
                print(" " * 150, end="\r")  # Clear the line

    # Save prompts json to EarwaxPrompts.jet
    print('Saving prompts to \033[94m"EarwaxPrompts.jet"\033[0m')
    prompts_jet_file = os.path.join(base_dir, "EarwaxPrompts.jet")
    with open(prompts_jet_file, "w") as f:
        json.dump(output_data, f)

    return output_data


# ----- JSON File Generation Functions -----


def create_earwax_audio_jet(base_dir, files):
    print('Creating \033[94m"EarwaxAudio.jet"\033[0m')
    jet_file_path = os.path.join(base_dir, "EarwaxAudio.jet")

    with open(jet_file_path, "w") as newEarwaxAudio:
        # Write initial lines
        newEarwaxAudio.write('{\n\t"episodeid":1234,"content":\n\t[\n')

        # We need to do a preliminary write here to avoid comma issues at the end
        newEarwaxAudio.write(
            '\t\t{"x":false,"name":"'
            + files[0]
            + '","short":"'
            + files[0]
            + '","id":"'
            + files[0]
            + '","categories":["household"]}'
        )

        # Write the line for every file
        for file in files:
            if file == files[0]:
                continue
            newEarwaxAudio.write(
                ',\n\t\t{"x":false,"name":"'
                + file
                + '","short":"'
                + file
                + '","id":"'
                + file
                + '","categories":["household"]}'
            )

        # Write final lines
        newEarwaxAudio.write("\n\t]\n}")

    print('\033[94m"EarwaxAudio.jet"\033[0m file created')


# ----- File Copy and Merge Functions -----


def copy_files_to_game_folders(base_dir, earwax_content):
    # Copy all .ogg files from the local New Sounds folder to earwax_content\EarwaxAudio\Audio
    new_sounds_path = os.path.join(base_dir, "New Sounds")
    earwax_audio_path = os.path.join(earwax_content, "EarwaxAudio", "Audio")

    total_files_copied = 0
    for filename in os.listdir(new_sounds_path):
        if filename.endswith(".ogg"):
            source_file_path = os.path.join(new_sounds_path, filename)
            destination_file_path = os.path.join(earwax_audio_path, filename)
            print(" " * 150, end="\r")  # Clear the line
            print(
                f'Copying \033[94m"{filename}"\033[0m to EarwaxAudio/Audio folder',
                end="\r",
            )
            with open(source_file_path, "rb") as src_file:
                with open(destination_file_path, "wb") as dst_file:
                    dst_file.write(src_file.read())
            total_files_copied += 1
            print(" " * 150, end="\r")  # Clear the line
    print("Finished Copying New Audio Files")
    print(
        f"Total files copied to EarwaxAudio/Audio folder: \033[94m{total_files_copied}\033[0m"
    )

    # Copy all .jet files from the local Spectrum folder to earwax_content\EarwaxAudio\Spectrum
    spectrum_path = os.path.join(base_dir, "Spectrum")
    earwax_spectrum_path = os.path.join(earwax_content, "EarwaxAudio", "Spectrum")

    total_files_copied = 0
    for filename in os.listdir(spectrum_path):
        if filename.endswith(".jet"):
            source_file_path = os.path.join(spectrum_path, filename)
            destination_file_path = os.path.join(earwax_spectrum_path, filename)
            print(" " * 150, end="\r")  # Clear the line
            print(
                f'Copying \033[94m"{filename}"\033[0m to EarwaxAudio/Spectrum folder',
                end="\r",
            )
            with open(source_file_path, "rb") as src_file:
                with open(destination_file_path, "wb") as dst_file:
                    dst_file.write(src_file.read())
            total_files_copied += 1
            print(" " * 150, end="\r")  # Clear the line
    print("Finished Copying New Spectrum Files")
    print(
        f"Total files copied to EarwaxAudio/Spectrum folder: \033[94m{total_files_copied}\033[0m"
    )

    # Copy all .ogg files from the local EarwaxPrompts folder to earwax_content\EarwaxPrompts
    local_earwax_prompts_path = os.path.join(base_dir, "EarwaxPrompts")
    if os.path.exists(local_earwax_prompts_path):
        earwax_prompts_destination_path = os.path.join(earwax_content, "EarwaxPrompts")

        total_files_copied = 0
        for filename in os.listdir(local_earwax_prompts_path):
            if filename.endswith(".ogg"):
                source_file_path = os.path.join(local_earwax_prompts_path, filename)
                destination_file_path = os.path.join(
                    earwax_prompts_destination_path, filename
                )
                print(" " * 150, end="\r")  # Clear the line
                print(
                    f'Copying \033[94m"{filename}"\033[0m to EarwaxPrompts folder',
                    end="\r",
                )
                with open(source_file_path, "rb") as src_file:
                    with open(destination_file_path, "wb") as dst_file:
                        dst_file.write(src_file.read())
                total_files_copied += 1
                print(" " * 150, end="\r")  # Clear the line
        print("Finished Copying New Prompt Files")
        print(
            f"\nTotal files copied to EarwaxPrompts folder: \033[94m{total_files_copied}\033[0m"
        )


def merge_jet_files(base_dir, earwax_content):
    # Merge the content of the new EarwaxAudio.jet file into the existing EarwaxAudio.jet file
    existing_earwax_audio_path = os.path.join(earwax_content, "EarwaxAudio.jet.bak")
    destination_earwax_audio_path = os.path.join(earwax_content, "EarwaxAudio.jet")
    local_earwax_audio_path = os.path.join(base_dir, "EarwaxAudio.jet")

    print(
        f'Merging content from \033[94m"EarwaxAudio.jet"\033[0m into \033[94m"{destination_earwax_audio_path}"\033[0m'
    )
    try:
        with open(existing_earwax_audio_path, "r", encoding="utf-8") as existing_file:
            existing_data = json.load(existing_file)
    except FileNotFoundError:
        existing_data = {"episodeid": 1234, "content": []}

    with open(local_earwax_audio_path, "r", encoding="utf-8") as new_file:
        new_data = json.load(new_file)

    # Merge the content
    existing_data["content"].extend(new_data["content"])

    # Remove duplicates based on 'id'
    unique_content = {item["id"]: item for item in existing_data["content"]}.values()
    existing_data["content"] = list(unique_content)

    # Write the merged content back to the existing EarwaxAudio.jet file
    with open(destination_earwax_audio_path, "w", encoding="utf-8") as merged_file:
        json.dump(existing_data, merged_file, indent=4)

    # Merge the content of the new EarwaxPrompts.jet file into the existing EarwaxPrompts.jet file
    existing_earwax_prompts_path = os.path.join(earwax_content, "EarwaxPrompts.jet.bak")
    destination_earwax_prompts_path = os.path.join(earwax_content, "EarwaxPrompts.jet")
    local_earwax_prompts_path = os.path.join(base_dir, "EarwaxPrompts.jet")

    if os.path.exists(local_earwax_prompts_path):
        print(
            f'Merging content from \033[94m"EarwaxPrompts.jet"\033[0m into \033[94m"{destination_earwax_prompts_path}"\033[0m'
        )
        try:
            with open(
                existing_earwax_prompts_path, "r", encoding="utf-8"
            ) as existing_file:
                existing_prompts_data = json.load(existing_file)
        except FileNotFoundError:
            existing_prompts_data = {"content": []}

        with open(local_earwax_prompts_path, "r", encoding="utf-8") as new_file:
            new_prompts_data = json.load(new_file)

        # Merge the content
        existing_prompts_data["content"].extend(new_prompts_data["content"])

        # Remove duplicates based on 'id'
        unique_prompts_content = {
            item["id"]: item for item in existing_prompts_data["content"]
        }.values()
        existing_prompts_data["content"] = list(unique_prompts_content)

        # Write the merged content back to the existing EarwaxPrompts.jet file
        with open(
            destination_earwax_prompts_path, "w", encoding="utf-8"
        ) as merged_file:
            json.dump(existing_prompts_data, merged_file, indent=4)


# ----- Main Function -----


def main():
    base_dir = os.getcwd()

    if not is_libsndfile_installed():
        install_libsndfile()

    if not is_rubberband_installed():
        install_rubberband()

    # Step 1: Locate Jackbox Path and Earwax content directory
    jackbox_path, earwax_content = locate_jackbox_path()

    # Step 2: Create backups of original files
    create_backups(earwax_content)

    # Step 3: Copy prompt files if needed
    local_source_voice_path = os.path.join(base_dir, "source_voice")
    copy_prompt_files(earwax_content, local_source_voice_path)

    # Step 4: Set up and process audio files in New Sounds directory
    sounds_dir = os.path.join(base_dir, "New Sounds")
    convert_audio_files(sounds_dir)

    # Return to base directory
    os.chdir(base_dir)

    # Step 5: Generate spectrum files
    files = generate_spectrum_files(sounds_dir, base_dir)

    # Step 6: Process TTS files if needed
    source_voice = prepare_source_voice(base_dir)
    generate_prompts(base_dir, source_voice)

    # Step 7: Create EarwaxAudio.jet file
    create_earwax_audio_jet(base_dir, files)

    # Step 8: Copy files to game folders
    copy_files_to_game_folders(base_dir, earwax_content)

    # Step 9: Prompt to choose whether to merge into original earwax sounds, or include only our new sounds
    choice = (
        input(
            "Do you want to merge into original earwax sounds (yes) or include only our new sounds (no)? (yes/no): "
        )
        .strip()
        .lower()
    )
    if choice == "yes":
        merge_jet_files(base_dir, earwax_content)
    else:
        print("Skipping merge. Only new sounds will be included.")
        # Copy our new EarwaxAudio.jet file to the game folder
        destination_earwax_audio_path = os.path.join(earwax_content, "EarwaxAudio.jet")
        local_earwax_audio_path = os.path.join(base_dir, "EarwaxAudio.jet")
        with open(local_earwax_audio_path, "rb") as src_file:
            with open(destination_earwax_audio_path, "wb") as dst_file:
                dst_file.write(src_file.read())

    # Step 10: Offer to launch Earwax directly if it was located automatically
    if located_automatically:
        launch_choice = (
            input("Would you like to launch Earwax now? (yes/no): ").strip().lower()
        )
        if launch_choice == "yes":
            print("Launching Earwax...")
            os.startfile(
                "steam://run/397460//-launchTo games%2FEarwax%2FEarwax.swf -jbg.config isBundle=false"
            )

        else:
            print("Complete!")

    # And collect garbage
    gc.collect()


if __name__ == "__main__":
    main()
