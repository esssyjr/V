import io
import os
import wave
from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import JSONResponse
from google.cloud import speech
from google.cloud import translate_v2 as translate
from google.cloud import texttospeech
from pydub import AudioSegment  # NEW: for audio conversion

# ======================
# GOOGLE CLOUD CREDS
# ======================
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "sapient-logic-470202-h4-7662fe9208aa.json"

# ======================
# LANGUAGE OPTIONS (STT + TTS + Translation supported)
# ======================
language_options = {
    "English (US)": ("en", "en-US"),
    "French (France)": ("fr", "fr-FR"),
    "Spanish": ("es", "es-ES"),
    "German": ("de", "de-DE"),
    "Italian": ("it", "it-IT"),
    "Japanese": ("ja", "ja-JP"),
    "Korean": ("ko", "ko-KR"),
    "Portuguese (Brazil)": ("pt", "pt-BR"),
    "Russian": ("ru", "ru-RU"),
    "Hindi": ("hi", "hi-IN"),
    "Indonesian": ("id", "id-ID"),
    "Turkish": ("tr", "tr-TR"),
    "Vietnamese": ("vi", "vi-VN"),
    "Thai": ("th", "th-TH"),
    "Ukrainian": ("uk", "uk-UA"),
    "Arabic": ("ar", "ar-EG"),
    "Chinese (Simplified)": ("zh", "cmn-Hans-CN"),
}

# ======================
# UTIL FUNCTIONS
# ======================
def convert_to_wav(input_file, output_file="converted.wav"):
    """Convert any audio file to 16kHz mono PCM WAV"""
    audio = AudioSegment.from_file(input_file)
    audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
    audio.export(output_file, format="wav")
    return output_file

def speech_to_text(audio_file, language_code="en-US"):
    client = speech.SpeechClient()
    with io.open(audio_file, "rb") as f:
        content = f.read()
    with wave.open(audio_file, "rb") as wf:
        sample_rate = wf.getframerate()

    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=sample_rate,
        language_code=language_code,
    )
    response = client.recognize(config=config, audio=audio)

    text = ""
    for result in response.results:
        text += result.alternatives[0].transcript
    return text

def translate_text(text, target_language):
    translate_client = translate.Client()
    result = translate_client.translate(text, target_language=target_language)
    return result["translatedText"]

def text_to_speech_file(text, language_code="en-US", filename="output.wav"):
    client = texttospeech.TextToSpeechClient()
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16
    )

    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    with open(filename, "wb") as out:
        out.write(response.audio_content)
    return filename

# ======================
# FASTAPI APP
# ======================
app = FastAPI(title="🌍 Modular Speech Translator API")

@app.get("/")
def root():
    return {"message": "Welcome to the Speech Translator API", "available_endpoints": ["/stt", "/translate", "/tts"]}

# ======================
# STT (Speech → Text)
# ======================
@app.post("/stt")
async def stt(audio: UploadFile, source_lang: str = Form(...)):
    if source_lang not in language_options:
        return JSONResponse(status_code=400, content={"error": "Unsupported source language."})
    
    source_lang_code = language_options[source_lang][1]
    temp_audio = "input_" + audio.filename
    with open(temp_audio, "wb") as f:
        f.write(await audio.read())

    # Convert uploaded file (m4a/mp3/wav) → wav for Google
    wav_file = convert_to_wav(temp_audio)

    text = speech_to_text(wav_file, language_code=source_lang_code)
    return {"recognized_text": text}

# ======================
# Translation (Text → Text)
# ======================
@app.post("/translate")
async def translation(text: str = Form(...), target_lang: str = Form(...)):
    if target_lang not in language_options:
        return JSONResponse(status_code=400, content={"error": "Unsupported target language."})
    
    target_lang_short, _ = language_options[target_lang]
    translated_text = translate_text(text, target_lang_short)
    return {"translated_text": translated_text}

# ======================
# TTS (Text → Speech)
# ======================
@app.post("/tts")
async def tts(text: str = Form(...), target_lang: str = Form(...)):
    if target_lang not in language_options:
        return JSONResponse(status_code=400, content={"error": "Unsupported target language."})
    
    _, target_lang_code = language_options[target_lang]
    output_audio = text_to_speech_file(text, language_code=target_lang_code)
    return {"audio_file": output_audio}
