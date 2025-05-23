from google.cloud import speech


def transcript_audio(content: bytes) -> str:
    # Instantiates a client
    client = speech.SpeechClient()

    audio = speech.RecognitionAudio(content=content)

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="fr-FR",
    )

    # Detects speech in the audio file
    response = client.recognize(config=config, audio=audio)

    transcript = ""

    for result in response.results:
        transcript += result.alternatives[0].transcript

    return transcript


def transcript_audio_webm(content: bytes) -> str:
    """Transcribe WebM/Opus audio content directly"""
    # Instantiates a client
    client = speech.SpeechClient()

    audio = speech.RecognitionAudio(content=content)

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
        # sample_rate_hertz is not needed for WEBM_OPUS as it's auto-detected
        language_code="fr-FR",
        enable_automatic_punctuation=True,
        model="latest_long",  # Better for short audio clips
    )

    # Detects speech in the audio file
    response = client.recognize(config=config, audio=audio)

    transcript = ""

    for result in response.results:
        transcript += result.alternatives[0].transcript

    return transcript


def transcript_audio_by_uri(uri: str) -> speech.RecognizeResponse:
    # Instantiates a client
    client = speech.SpeechClient()

    audio = speech.RecognitionAudio(uri=uri)

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="en-US",
    )

    # Detects speech in the audio file
    response = client.recognize(config=config, audio=audio)

    for result in response.results:
        print(f"Transcript: {result.alternatives[0].transcript}")
