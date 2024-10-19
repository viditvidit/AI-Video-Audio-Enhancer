# There are 2 solutions for this POC:

### Method 1: Using Markers to sync audio and video

In this method, the audio regenerated from the Google Cloud TTS uses reference markers to sync the generated audio with the input video.

### Method 2: Syncing audio and video by trimming

In this method, the duration of audio generated is taken into consideration, the video is accordingly trimmed in order to maintain evenness and later the newly generated audio is merged onto the trimmed video as the output.

## Both solutions make use of user input credentials for ease of use.
