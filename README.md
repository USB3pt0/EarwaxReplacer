# EarwaxReplacer

A Python script to add sounds in The Jackbox Party Pack 2's game Earwax.

This utility allows users to customize the sounds in The Jackbox Party Pack 2's Earwax game by adding their own audio files and generating the required metadata and spectrum files for the game to function correctly.

1. Locates the Jackbox path and Earwax content directory (automatic for steam version).
2. Creates backups of original `.jet` files.
3. Copies original prompt files from Earwax as reference for TTS model generation.
4. Converts your audio files present in the New Sounds directory.
5. Generates spectrum files for each new audio file.
6. Generates new prompt audio files based on the lines in prompts.txt using TTS
7. Creates the EarwaxAudio.jet and EarwaxPrompts.jet files.
8. Copies new audio files to game folders.
9. Prompts the user to choose whether to merge our new sounds into original Earwax sounds or include only new sounds.
10. Merges or copies the EarwaxAudio.jet and EarwaxPrompts.jet files based on user choice.
11. Offers to launch the game directly (steam version only).

## Setup Instructions

### 1. Install Python 3.10

To install Python 3.10 from PowerShell, follow these steps:

1. Open PowerShell and run the following command to download the installer:

   ```sh
   Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.10.0/python-3.10.0-amd64.exe" -OutFile "python-3.10.0-amd64.exe"
   ```

2. Run the installer with the following command:

   ```sh
   Start-Process -FilePath "python-3.10.0-amd64.exe" -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait
   ```

3. Verify the installation by running:
   ```sh
   python --version
   ```

### 2. Install Dependencies

1. Open a terminal in Visual Studio Code.
2. Navigate to your project directory:
   ```sh
   cd \my\path\to\EarwaxReplacer
   ```
3. Install the dependencies from `requirements.txt`:
   ```sh
   pip install -r requirements.txt
   ```

### 3. Running the Script

1. Run the script:
   ```sh
   python EarwaxReplacer.py
   ```

### 4. Additional Information

- The script will attempt to automatically locate the Jackbox Party Pack 2 installation path and create backups of the original `.jet` files.
- It will also handle copying prompt files, processing audio files, generating spectrum files, and creating necessary `.jet` files.
- You will be prompted at the end to choose whether to include the original game sounds, or only your new sounds.

### 5. Requirements

The `requirements.txt` file should include the following dependencies:

```
numpy
torch
soundfile
pyrubberband
scipy
pydub
TTS
```

### 6. Troubleshooting

If you encounter any issues, ensure that:

- Python 3.10 is correctly installed and added to your system PATH.
- All dependencies are installed without errors.
