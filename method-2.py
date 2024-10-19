import streamlit as st
import moviepy.editor as mp
import io
import os
from google.cloud import speech, texttospeech
from pydub import AudioSegment
import requests  # For API calls
import tempfile

# Initialize Google Cloud clients
speech_client = speech.SpeechClient()
tts_client = texttospeech.TextToSpeechClient()


def correct_text(transcription):
    url = "https://internshala.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-08-01-preview"
    headers = {
        "Content-Type": "application/json",
        "api-key": "22ec84421ec24230a3638d1b51e3a7dc"  # Replace with your API key
    }
    payload = {
        "messages": [
            {"role": "user",
             "content": f"Transform the following transcription into coherent and natural sentences while correcting grammatical mistakes and removing fillers like 'um' and 'uh': {transcription}"}
        ],
        "max_tokens": 500
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        st.error("Error in GPT-4o API request.")
        return transcription  # Return original transcription if error


# Function to transcribe audio
def transcribe_audio(audio_file):
    audio_segment = AudioSegment.from_file(audio_file, format='wav')
    sample_rate = audio_segment.frame_rate
    audio_segment = audio_segment.set_channels(1)

    # Use a temporary file for audio
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav_file:
        audio_segment.export(temp_wav_file.name, format='wav')
        temp_wav_file.seek(0)

    with open(temp_wav_file.name, 'rb') as audio_file:
        audio_content = audio_file.read()

    audio = speech.RecognitionAudio(content=audio_content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=sample_rate,
        language_code="en-US",
    )

    response = speech_client.recognize(config=config, audio=audio)
    transcription = " ".join([result.alternatives[0].transcript for result in response.results])

    return transcription


# Function to synthesize speech
def synthesize_speech(text):
    input_text = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        name="en-US-Wavenet-D"
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    response = tts_client.synthesize_speech(
        input=input_text, voice=voice, audio_config=audio_config
    )

    synthesized_audio = AudioSegment.from_mp3(io.BytesIO(response.audio_content))
    return synthesized_audio


# Function to replace audio in the original video
def replace_audio(original_video_file, new_audio):
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio_file:
        new_audio.export(temp_audio_file.name, format='mp3')

    original_video = mp.VideoFileClip(original_video_file)
    new_audio_clip = mp.AudioFileClip(temp_audio_file.name)

    final_video = original_video.set_audio(new_audio_clip)

    output_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
    final_video.write_videofile(output_file, codec='libx264', audio_codec="aac")  # Ensure proper codec

    return output_file

# Streamlit UI
st.title("Video Audio Replacement with AI Generated Voice (Sync Sentences)")
st.subheader("This approach adjusts audio by syncing sentences by using markers")


uploaded_video = st.file_uploader("Upload Video", type=["mp4", "mov"])
if uploaded_video:
    st.video(uploaded_video)

    if st.button("Replace Audio"):
        # Save uploaded video to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video_file:
            temp_video_file.write(uploaded_video.read())
            video_path = temp_video_file.name

        video = mp.VideoFileClip(video_path)
        duration = video.duration

        if duration > 30:  # Only split if the video is longer than 30 seconds
            # Split the video into two halves
            half_duration = duration / 2

            # Process the first half
            first_half = video.subclip(0, half_duration)
            first_half_audio_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
            first_half.audio.write_audiofile(first_half_audio_path)

            first_transcription = transcribe_audio(first_half_audio_path)
            st.write("Transcription of first half:", first_transcription)

            first_corrected_text = correct_text(first_transcription)
            st.write("Corrected Text of first half:", first_corrected_text)

            first_synthesized_audio = synthesize_speech(first_corrected_text)

            # Process the second half
            second_half = video.subclip(half_duration, duration)
            second_half_audio_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
            second_half.audio.write_audiofile(second_half_audio_path)

            second_transcription = transcribe_audio(second_half_audio_path)
            st.write("Transcription of second half:", second_transcription)

            second_corrected_text = correct_text(second_transcription)
            st.write("Corrected Text of second half:", second_corrected_text)

            second_synthesized_audio = synthesize_speech(second_corrected_text)

            # Merge the two synthesized audios
            final_audio = first_synthesized_audio + second_synthesized_audio

        else:
            # Process the entire video if it's 30 seconds or shorter
            audio_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
            video.audio.write_audiofile(audio_path)

            transcription = transcribe_audio(audio_path)
            st.write("Transcription of video:", transcription)

            corrected_text = correct_text(transcription)
            st.write("Corrected Text of video:", corrected_text)

            final_audio = synthesize_speech(corrected_text)

        # Replace audio in the original video with synthesized audio
        final_video_path = replace_audio(video_path, final_audio)

        st.success("Audio replaced successfully!")
        st.video(final_video_path)

        # Clean up temporary files
        os.remove(video_path)

        if duration > 30:
            if os.path.exists(first_half_audio_path):
                os.remove(first_half_audio_path)
            if os.path.exists(second_half_audio_path):
                os.remove(second_half_audio_path)

        if 'audio_path' in locals() and os.path.exists(audio_path):
            os.remove(audio_path)  # Remove the audio path if used