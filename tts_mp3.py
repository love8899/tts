import os
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk

load_dotenv()

key = os.getenv("AZURE_SPEECH_KEY")
region = os.getenv("AZURE_SPEECH_REGION")

text = "Hello! This is Azure Text to Speech generating an MP3 file."
voice = "en-US-JennyNeural"
out_file = "output.mp3"

speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
speech_config.speech_synthesis_voice_name = voice

audio_config = speechsdk.audio.AudioOutputConfig(filename=out_file)
synth = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

result = synth.speak_text_async(text).get()

if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
    print("OK ->", out_file)
else:
    print("FAILED")

