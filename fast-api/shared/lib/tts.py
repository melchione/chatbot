import google.cloud.texttospeech as tts
import re


def text_to_wav(text: str):
    voice_name = "fr-FR-Chirp-HD-D"
    language_code = "-".join(voice_name.split("-")[:2])
    text_input = tts.SynthesisInput(text=text)
    voice_params = tts.VoiceSelectionParams(
        language_code=language_code, name=voice_name
    )
    audio_config = tts.AudioConfig(audio_encoding=tts.AudioEncoding.LINEAR16)

    client = tts.TextToSpeechClient()
    response = client.synthesize_speech(
        input=text_input,
        voice=voice_params,
        audio_config=audio_config,
    )

    filename = f"{voice_name}.wav"
    with open(filename, "wb") as out:
        out.write(response.audio_content)
        print(f'Generated speech saved to "{filename}"')


def text_to_audio_bytes(text: str) -> bytes:
    """
    Convertit du texte en audio et retourne les bytes audio.
    Nettoie d'abord le markdown du texte.
    """
    # Nettoyer le markdown
    clean_text = clean_markdown_for_speech(text)

    if not clean_text.strip():
        raise ValueError("Le texte nettoyé est vide")

    voice_name = "fr-FR-Chirp-HD-D"
    language_code = "-".join(voice_name.split("-")[:2])
    text_input = tts.SynthesisInput(text=clean_text)
    voice_params = tts.VoiceSelectionParams(
        language_code=language_code, name=voice_name
    )
    # Utiliser MP3 pour une meilleure compression sur le web
    audio_config = tts.AudioConfig(audio_encoding=tts.AudioEncoding.MP3)

    client = tts.TextToSpeechClient()
    response = client.synthesize_speech(
        input=text_input,
        voice=voice_params,
        audio_config=audio_config,
    )

    return response.audio_content


def clean_markdown_for_speech(text: str) -> str:
    """
    Nettoie le texte markdown et HTML pour la synthèse vocale.
    """
    # Supprimer les balises HTML complètement
    text = re.sub(r"<[^>]+>", "", text)

    # Supprimer les entités HTML
    text = re.sub(r"&[a-zA-Z]+;", "", text)
    text = re.sub(r"&#?\w+;", "", text)

    # Supprimer les titres markdown (# ## ###)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Supprimer les liens markdown [texte](url) -> garder juste le texte
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

    # Supprimer le texte en gras et italique mais garder le contenu
    text = re.sub(r"\*\*([^\*]+?)\*\*", r"\1", text)  # **gras**
    text = re.sub(r"\*([^\*]+?)\*", r"\1", text)  # *italique*
    text = re.sub(r"__([^_]+?)__", r"\1", text)  # __gras__
    text = re.sub(r"_([^_]+?)_", r"\1", text)  # _italique_

    # Supprimer les codes inline `code`
    text = re.sub(r"`([^`]+?)`", r"\1", text)

    # Supprimer les blocs de code ```
    text = re.sub(r"```[\s\S]*?```", "", text)

    # Supprimer les listes markdown (- ou * au début de ligne)
    text = re.sub(r"^[-\*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)  # listes numérotées

    # Supprimer les citations (>)
    text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)

    # Supprimer les lignes horizontales
    text = re.sub(r"^[-_*]{3,}$", "", text, flags=re.MULTILINE)

    # Supprimer les caractères markdown restants
    text = re.sub(r"[*_`~^]", "", text)  # caractères markdown isolés
    text = re.sub(r"[<>]", "", text)  # chevrons HTML restants
    text = re.sub(r"[{}]", "", text)  # accolades
    text = re.sub(r"[\[\]]", "", text)  # crochets

    # Supprimer les doubles espaces et caractères spéciaux indésirables
    text = re.sub(r"[|\\]", "", text)  # pipes et backslashes
    text = re.sub(r"#+", "", text)  # hash restants

    # Remplacer les caractères spéciaux par des équivalents prononcables
    text = re.sub(r"&", " et ", text)
    text = re.sub(r"@", " arobase ", text)
    text = re.sub(r"%", " pour cent ", text)
    text = re.sub(r"\$", " dollars ", text)
    text = re.sub(r"€", " euros ", text)

    # Supprimer les émojis
    text = re.sub(
        r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002600-\U000027BF\U0001F900-\U0001F9FF]",
        "",
        text,
    )

    # Nettoyer les espaces et sauts de ligne multiples
    text = re.sub(r"\n+", " ", text)  # remplacer sauts de ligne par espaces
    text = re.sub(r"\s+", " ", text)  # réduire espaces multiples
    text = re.sub(r"\s*[.]{2,}\s*", ". ", text)  # points multiples -> point simple
    text = re.sub(r"\s*[!]{2,}\s*", "! ", text)  # exclamations multiples
    text = re.sub(r"\s*[?]{2,}\s*", "? ", text)  # interrogations multiples

    # Ajouter des pauses naturelles pour la lecture
    text = re.sub(r"([.!?])\s*([A-Z])", r"\1 \2", text)  # pause après ponctuation
    text = re.sub(
        r"([,;:])", r"\1 ", text
    )  # petite pause après virgules/points-virgules

    return text.strip()
