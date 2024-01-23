# EarwaxReplacer
A Python script to replace the default sounds in The Jackbox Party Pack 2's game Earwax.

This script is designed to take a folder of sounds in .ogg format and create an associated dummy spectrum waveform script file, and a new sounds script file for Earwax to load the sounds.
This was hastily made by me, for me, so it won't convert files, trim them, or change their volume, and has some caveats to follow:
1. The game will not work without spectrum files for each file, so make sure one exists for each.
2. The ThreeTwoOne.jet file in the default Spectrum folder is integral; the game WILL NOT START without it!
3. You must have the folders "New Sounds" and  "Spectrum" in the directory where you have the python script.
4. There must be at least 6 sounds for every player or the game will fail to continue.
5. The script takes the filename and strips the .ogg from it; whatever the filename is, will be what the sound is named in-game.

# How To Use:
1. Create the folders New Sounds and Spectrum wherever you have the .py script.
2. Open New Sounds and put ONLY sounds in .ogg format in the folder.  No idea what happens when you try other ones; it probably breaks.  Give your files a reasonably descriptive filename, as the filename is what it will show up as in-game.
3. Run Earwax Replacer.py.  I do it from command line, but it should work fine just double clicking.
4. Copy resultant sounds, spectrum files, and EarwaxAudio.jet to the proper locations (back up the originals, leaving ThreeTwoOne.jet in the Spectrum folder intact).  You will find them in The Jackbox Party Pack 2\games\Earwax\content if you downloaded from Steam.
5. Run Earwax and enjoy your modded game!

# To-Do:
1. GUI interface.
2. Allow user to select directories.
3. Allow user to rename sounds rather than use filenames.
4. Include a .ogg conversion script so you and I don't have to do it manually by hand in Foobar2000.

# Possible future features:
1. Custom prompts.  With an empty .ogg file for M.O.T.H.E.R.'s voice, anything can be set as a prompt.  That said, I will probably make a separate script with input fields for that rather than try to wrap them both up in one script.  I did have the idea of using lines from video games as prompts, and those could easily be imported as oggs...
2. Keeping some sounds from stock Earwax.  That will require a full app and maybe even hardcoding their lines in, so they can be appended to the EarwaxAudio.jet.  You can hack it now by opening the stock EarwaxAudio.jet and copying the lines you need.  Use a code beautifier though because it is a mess only organized by id number/filename.  You could also just copy the associated ogg and rename it and use this script, I guess...
