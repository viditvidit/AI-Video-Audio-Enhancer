import streamlit
import pydub
import moviepy.editor as mp
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import texttospeech
import openai
import os
import requests
import tempfile

#Google Cloud credentials and OpenAI API key
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/vidit/Downloads/clear-vision-438804-u6-9e0e3ffd8ef8.json"
openai.api_key = "22ec84421ec24230a3638d1b51e3a7dc"


#1 - Transcribing the original audio using Google Speech-to-Text
def transcribe_audio(audio_file):
    client = speech.SpeechClient()
    with open(audio_file, "rb") as audio_content:
        content = audio_content.read()
    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=44100,
        language_code="en-US",
        enable_automatic_punctuation=True,
    )
    response = client.recognize(config=config, audio=audio)
    transcript = ""
    for result in response.results:
        transcript += result.alternatives[0].transcript
    return transcript

#2 - Correcting the transcription using GPT-4o API (via Azure)
def correct_text(transcription):
    url = "https://internshala.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-08-01-preview"
    headers = {
        "Content-Type": "application/json",
        "api-key": "22ec84421ec24230a3638d1b51e3a7dc"
    }
    payload = {
        "messages": [
            {"role": "user",
             "content": f"Correct the following transcription for grammatical mistakes and remove fillers like 'um' and 'hmm' and only return the transcription: {transcription}"}
        ],
        "max_tokens": 500
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        streamlit.error(f"Error in GPT-4o API request: {response.status_code} - {response.text}")
        return transcription  # Return original transcription if error

#3 - Generating new audio using Google Text-to-Speech
def generate_audio(text):
    client = texttospeech.TextToSpeechClient()
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        name="en-US-Wavenet-D",
        language_code="en-GB",
    )
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16)
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as out:
        out.write(response.audio_content)
        return out.name

#4 - Trimming the video based on the duration of the generated audio
def trim_video(video_path, audio_path):
    audio = pydub.AudioSegment.from_wav(audio_path)
    audio_duration = len(audio) / 1000.0  # Duration in seconds
    video = mp.VideoFileClip(video_path)
    trimmed_video = video.subclip(0, audio_duration)
    trimmed_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    trimmed_video.write_videofile(trimmed_video_path, codec="libx264", audio_codec="aac")
    return trimmed_video_path


#5 - Replacing the audio of the trimmed video with the generated audio
def replace_audio(video_path, audio_path):
    video = mp.VideoFileClip(video_path)
    audio = mp.AudioFileClip(audio_path)
    final_video = video.set_audio(audio)
    final_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    final_video.write_videofile(final_video_path, codec="libx264", audio_codec="aac")
    return final_video_path

#Streamlit UI for video processing
streamlit.title("Video Audio Enhancement with AI")
streamlit.subheader("This approach adjusts the output based on regenerated audio by trimming the video to match the new audio's duration")
streamlit.caption("Created by Vidit Kharecha")

uploaded_file = streamlit.file_uploader("Upload Video", type=["mp4", "mov"])

if uploaded_file is not None:
    #Saving the uploaded video
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as f:
        f.write(uploaded_file.read())
        video_path = f.name
    video = mp.VideoFileClip(video_path)
    duration = video.duration

    #Extracting audio and process it
    audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
    video.audio.write_audiofile(audio_path)

    #Convert to mono
    sound = pydub.AudioSegment.from_wav(audio_path)
    sound = sound.set_channels(1)
    sound.export(audio_path, format="wav")  # Overwrite the original

    if duration > 30:
        #SPlitting the audio into two halves
        half_duration = duration / 2
        first_half = video.subclip(0, half_duration)
        second_half = video.subclip(half_duration, duration)

        #Processing first half
        first_half_audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        first_half.audio.write_audiofile(first_half_audio_path)

        #Converting to mono
        sound = pydub.AudioSegment.from_wav(first_half_audio_path)
        sound = sound.set_channels(1)
        sound.export(first_half_audio_path, format="wav")  # Overwrite the original

        first_transcript = transcribe_audio(first_half_audio_path)
        streamlit.write("Transcription of first half:", first_transcript)

        first_corrected_text = correct_text(first_transcript)
        streamlit.write("Corrected Text of first half:", first_corrected_text)

        first_synthesized_audio = generate_audio(first_corrected_text)

        #Processing second half
        second_half_audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        second_half.audio.write_audiofile(second_half_audio_path)

        #Converting to mono
        sound = pydub.AudioSegment.from_wav(second_half_audio_path)
        sound = sound.set_channels(1)
        sound.export(second_half_audio_path, format="wav")  # Overwrite the original

        second_transcript = transcribe_audio(second_half_audio_path)
        streamlit.write("Transcription of second half:", second_transcript)

        second_corrected_text = correct_text(second_transcript)
        streamlit.write("Corrected Text of second half:", second_corrected_text)

        second_synthesized_audio = generate_audio(second_corrected_text)

        #Merging the two synthesized audios
        first_audio_segment = pydub.AudioSegment.from_wav(first_synthesized_audio)
        second_audio_segment = pydub.AudioSegment.from_wav(second_synthesized_audio)
        merged_audio = first_audio_segment + second_audio_segment

        #Saving the merged audio to a temporary file
        merged_audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        merged_audio.export(merged_audio_path, format="wav")

    else:
        #Processing the entire video if it's 30 seconds or shorter
        transcription = transcribe_audio(audio_path)
        streamlit.write("Transcription of video:", transcription)

        corrected_text = correct_text(transcription)
        streamlit.write("Corrected Text of video:", corrected_text)

        final_audio = generate_audio(corrected_text)

        #Using the synthesized audio directly for shorter videos
        merged_audio_path = final_audio

    #Trimming the original video based on the duration of the merged audio
    final_video_path = trim_video(video_path, merged_audio_path)

    #Replacing the original audio with the merged audio
    final_video_path = replace_audio(final_video_path, merged_audio_path)

    #Displaying the processed video
    streamlit.success("Video processed successfully!")
    streamlit.video(final_video_path)

    #Cleaning up temporary files
    try:
        os.remove(video_path)
        os.remove(audio_path)
        if duration > 30:
            os.remove(first_half_audio_path)
            os.remove(second_half_audio_path)
        os.remove(merged_audio_path)
    except FileNotFoundError:
        pass
else:
    streamlit.warning("Please upload a video file.")
