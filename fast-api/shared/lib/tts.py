import google.cloud.texttospeech as tts
import re
import asyncio
from google.adk.agents import LlmAgent
from pydantic import BaseModel

from features.agents.models import Models
from shared.lib.agent_runner import run_agent_with_retry


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


async def text_to_audio_bytes(text: str) -> bytes:
    """
    Convertit du texte en audio et retourne les bytes audio.
    Nettoie d'abord le markdown du texte.
    """
    # Nettoyer le markdown
    # clean_text = clean_markdown_for_speech(text)
    clean_text = await clean_markdown_for_speech_ai(text)

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


async def clean_markdown_for_speech_ai(text: str) -> str:
    """
    Nettoie le texte markdown pour une synthèse vocale naturelle.
    """

    class MdOutput(BaseModel):
        text: str

    agent = LlmAgent(
        model=Models.GEMINI_20_FLASH,
        name="text_to_json",
        instruction="Tu va recevoir un texte au format markdown. Tu dois nettoyer le texte pour une synthèse vocale naturelle.",
        description="Tu es un assistant qui nettoie le texte markdown pour une synthèse vocale naturelle.",  # Description utilisée comme base, mais l'input sera passé séparément
    )
    # Appel de la fonction utilitaire
    result = await run_agent_with_retry(
        agent=agent,
        user_input_text=text,
        output_schema=MdOutput,
    )

    return result["text"]


async def text_to_audio_bytes_async(text: str) -> bytes:
    """
    Convertit du texte en audio et retourne les bytes audio.
    Nettoie d'abord le markdown du texte.
    """
    clean_text = await clean_markdown_for_speech(text)
    return await asyncio.to_thread(text_to_audio_bytes, clean_text)


def clean_markdown_for_speech(text: str) -> str:
    """
    Transforme le texte markdown et HTML pour une synthèse vocale naturelle.
    """

    print("BEFORE", text)
    # Supprimer les balises HTML mais garder le contenu
    text = re.sub(r"<[^>]+>", "", text)

    # Supprimer les entités HTML
    text = re.sub(r"&[a-zA-Z]+;", "", text)
    text = re.sub(r"&#?\w+;", "", text)

    # Transformer les titres en phrases d'introduction
    text = re.sub(
        r"#{1,6}\s+([^#\n]+)", r"\1 ", text
    )  # Capturer tous les titres sans ajouter de ponctuation

    # Transformer les liens markdown en mentions naturelles
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"le lien \1", text)

    # Supprimer le formatage gras/italique mais garder le contenu avec emphase
    text = re.sub(r"\*\*([^\*]+?)\*\*", r"\1", text)  # **gras**
    text = re.sub(r"\*([^\*]+?)\*", r"\1", text)  # *italique*
    text = re.sub(r"__([^_]+?)__", r"\1", text)  # __gras__
    text = re.sub(r"_([^_]+?)_", r"\1", text)  # _italique_

    # Transformer les codes inline en description
    text = re.sub(r"`([^`]+?)`", r"le code \1", text)

    # Supprimer complètement les blocs de code
    text = re.sub(r"```[\s\S]*?```", " code omis ", text)

    # Transformer les listes à puces en énumération fluide
    # D'abord, identifier les groupes de listes
    def transform_bullet_list(match):
        lines = match.group(0).strip().split("\n")
        items = []
        for line in lines:
            # Nettoyer chaque élément de liste
            item = re.sub(r"^[-\*+]\s+", "", line.strip())
            if item:
                items.append(item)

        if len(items) == 1:
            return items[0]
        elif len(items) == 2:
            return f"{items[0]} et {items[1]}"
        else:
            # Pour 3+ éléments : "A, B, C et D"
            return ", ".join(items[:-1]) + f" et {items[-1]}"

    # Appliquer la transformation des listes à puces
    text = re.sub(
        r"(?:^[-\*+]\s+.+(?:\n|$))+", transform_bullet_list, text, flags=re.MULTILINE
    )

    # Transformer les listes numérotées en énumération avec connecteurs
    def transform_numbered_list(match):
        lines = match.group(0).strip().split("\n")
        items = []
        connectors = [
            "premièrement",
            "deuxièmement",
            "troisièmement",
            "quatrièmement",
            "cinquièmement",
        ]

        for i, line in enumerate(lines):
            item = re.sub(r"^\s*\d+\.\s+", "", line.strip())
            if item and i < len(connectors):
                items.append(f"{connectors[i]} {item}")
            elif item:
                items.append(f"ensuite {item}")

        return ". ".join(items) + "."

    # Appliquer la transformation des listes numérotées
    text = re.sub(
        r"(?:^\s*\d+\.\s+.+(?:\n|$))+",
        transform_numbered_list,
        text,
        flags=re.MULTILINE,
    )

    # Transformer les citations en attribution
    text = re.sub(r"^>\s*(.+)$", r"Je cite : \1", text, flags=re.MULTILINE)

    # Supprimer les lignes horizontales
    text = re.sub(r"^[-_*]{3,}$", "", text, flags=re.MULTILINE)

    # Remplacer les caractères spéciaux par des équivalents prononcables
    text = re.sub(r"&", " et ", text)
    text = re.sub(r"@", " arobase ", text)
    text = re.sub(r"%", " pour cent ", text)
    text = re.sub(r"\$", " dollars ", text)
    text = re.sub(r"€", " euros ", text)

    # Améliorer la prononciation des abréviations courantes
    text = re.sub(r"\betc\.", "et cetera", text)
    text = re.sub(r"\bex\.", "exemple", text)
    text = re.sub(r"\bcf\.", "voir", text)
    text = re.sub(r"\bp\.ex\.", "par exemple", text)
    text = re.sub(r"\bi\.e\.", "c'est-à-dire", text)
    text = re.sub(r"\be\.g\.", "par exemple", text)

    # Améliorer les connecteurs logiques
    text = re.sub(r"\bPS\b", "Post-scriptum", text)
    text = re.sub(r"\bNB\b", "Nota bene", text)

    # Supprimer les caractères markdown restants
    text = re.sub(r"[*_`~^]", "", text)  # caractères markdown isolés
    text = re.sub(r"[<>{}]", "", text)  # chevrons et accolades
    text = re.sub(r"[\[\]]", "", text)  # crochets
    text = re.sub(r"[|\\]", "", text)  # pipes et backslashes

    # Supprimer les émojis (nettoyage étendu pour éviter les mots fantômes)
    # Émojis de base
    text = re.sub(r"[\U0001F600-\U0001F64F]", "", text)  # Emoticons
    text = re.sub(r"[\U0001F300-\U0001F5FF]", "", text)  # Symboles et pictogrammes
    text = re.sub(r"[\U0001F680-\U0001F6FF]", "", text)  # Transport et cartes
    text = re.sub(r"[\U0001F1E0-\U0001F1FF]", "", text)  # Drapeaux
    text = re.sub(r"[\U00002600-\U000027BF]", "", text)  # Symboles divers
    text = re.sub(r"[\U0001F900-\U0001F9FF]", "", text)  # Émojis supplémentaires
    text = re.sub(r"[\U0001FA00-\U0001FAFF]", "", text)  # Nouveaux émojis
    text = re.sub(r"[\U00002700-\U000027BF]", "", text)  # Dingbats
    text = re.sub(r"[\U0000FE00-\U0000FE0F]", "", text)  # Sélecteurs de variation

    # Supprimer les caractères de contrôle et invisibles
    text = re.sub(r"[\u200B-\u200D\uFEFF]", "", text)  # Caractères de largeur zéro
    text = re.sub(r"[\u00AD\u061C\u180E]", "", text)  # Autres caractères invisibles

    # Améliorer la ponctuation pour des pauses naturelles
    text = re.sub(r"\s*[.]{2,}\s*", ". ", text)  # points multiples
    text = re.sub(r"\s*[!]{2,}\s*", " ! ", text)  # exclamations multiples
    text = re.sub(r"\s*[?]{2,}\s*", " ? ", text)  # interrogations multiples

    # Ajouter des pauses appropriées
    text = re.sub(r"([.!?])\s*([A-Z])", r"\1 \2", text)  # pause après ponctuation forte
    text = re.sub(r"([,;:])\s*", r"\1 ", text)  # petite pause après ponctuation faible
    text = re.sub(r":\s*([a-z])", r": \1", text)  # espace après deux-points

    # Nettoyer les espaces multiples
    text = re.sub(r"\n+", " ", text)  # remplacer sauts de ligne par espaces
    text = re.sub(r"\s+", " ", text)  # réduire espaces multiples

    print("AFTER", text)
    return text.strip()
