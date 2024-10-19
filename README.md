# The solutions make use of user input credentials for ease of use.

## There are 2 solutions for this POC:

### Method 1: Using Markers to sync audio and video
> Assumption: The user just wants the regenerated audio that includes fillers removed and grammatical mistakes corrected.

In this method, the audio regenerated from the Google Cloud TTS uses reference markers to sync the generated audio with the input video.

### Method 2: Syncing audio and video by trimming
> Assumption: The user wants the regenerated audio in such a way that it if in case the audio duration is shorter than that of the video, it is trimmed and processed.

In this method, the duration of audio generated is taken into consideration, the video is accordingly trimmed in order to maintain evenness and later the newly generated audio is merged onto the trimmed video as the output.
