<script>
    import { onMount } from "svelte";
    import { chatState, createNewSession } from "$lib/chatLogic.svelte.js";
    import { marked } from "marked";
    import { PUBLIC_FAST_API_URL } from "$env/static/public";

    const USER_ID = "test_user";

    // Configuration de marked pour la sécurité et les fonctionnalités
    marked.setOptions({
        breaks: true, // Convertit les sauts de ligne en <br>
        gfm: true, // Support GitHub Flavored Markdown
    });

    // Fonction pour parser le markdown et ajouter les classes Tailwind
    function parseMarkdown(/** @type {string} */ text) {
        try {
            let result = marked.parse(text);

            // Vérifier si c'est une string ou une Promise
            if (typeof result === "string") {
                // Post-traiter le HTML pour ajouter les classes Tailwind
                result = result
                    // Titres
                    .replace(
                        /<h1>/g,
                        '<h1 class="text-4xl font-extralight my-4">',
                    )
                    .replace(/<h2>/g, '<h2 class="text-2xl font-light my-3">')
                    .replace(/<h3>/g, '<h3 class="text-lg  my-2">')
                    .replace(/<h4>/g, '<h4 class="text-base  my-2">')
                    .replace(/<h5>/g, '<h5 class="text-sm  my-1">')
                    .replace(/<h6>/g, '<h6 class="text-xs  my-1">')
                    // Paragraphes
                    .replace(/<p>/g, '<p class="my-2">')
                    // Listes
                    .replace(/<ul>/g, '<ul class="my-2 pl-6 list-disc">')
                    .replace(/<ol>/g, '<ol class="my-2 pl-6 list-decimal">')
                    .replace(/<li>/g, '<li class="my-1">')
                    // Code inline et blocks
                    .replace(
                        /<code>/g,
                        '<code class="bg-gray-100 px-1 py-0.5 rounded text-sm font-mono break-all">',
                    )
                    .replace(
                        /<pre>/g,
                        '<pre class="bg-gray-100 p-4 rounded-lg overflow-x-auto my-3 w-full">',
                    )
                    // Citations
                    .replace(
                        /<blockquote>/g,
                        '<blockquote class="border-l-4 border-gray-400 pl-4 italic my-3 text-gray-600">',
                    )
                    // Liens
                    .replace(
                        /<a /g,
                        '<a class="text-blue-600 underline hover:no-underline break-all" ',
                    )
                    // Texte en gras et italique
                    .replace(/<strong>/g, '<strong class="font-bold">')
                    .replace(/<em>/g, '<em class="italic">')
                    // Tables (envelopper dans un conteneur scrollable complètement isolé)
                    .replace(
                        /<table>/g,
                        '<div class="w-full"><div class="overflow-x-auto max-w-[70vw] my-3"><table class="border-collapse border border-gray-300 w-max">',
                    )
                    .replace(/<\/table>/g, "</table></div></div>")
                    .replace(
                        /<th>/g,
                        '<th class="border border-gray-300 p-2 bg-gray-100 font-bold text-left whitespace-nowrap">',
                    )
                    .replace(
                        /<td>/g,
                        '<td class="border border-gray-300 p-2 whitespace-nowrap">',
                    );

                return result;
            } else {
                // Si c'est une Promise, on retourne le texte original pour éviter les erreurs
                console.warn(
                    "Marked returned a Promise, falling back to original text",
                );
                return text;
            }
        } catch (error) {
            console.error("Error parsing markdown:", error);
            return text; // Fallback au texte brut si erreur
        }
    }

    let messageInput = $state("");
    /** @type {HTMLDivElement | null} */
    let messagesArea = null;
    let autoScroll = $state(true);

    /** @type {File | null} */
    let selectedImageFile = $state(null);

    /** @type {HTMLInputElement | null} */
    let fileInput = null;

    // Nouvelles variables pour l'enregistrement audio
    /** @type {MediaRecorder | null} */
    let mediaRecorder = null;
    /** @type {MediaStream | null} */
    let audioStream = null;
    /** @type {AudioContext | null} */
    let audioContext = null;
    /** @type {AnalyserNode | null} */
    let analyser = null;
    /** @type {Float32Array | null} */
    let dataArray = null;
    let isRecording = $state(false);
    /** @type {ReturnType<typeof setTimeout> | null} */
    let recordingTimeout = null;
    /** @type {ReturnType<typeof setTimeout> | null} */
    let silenceTimeout = null;
    let recordingStartTime = 0;
    const MAX_RECORDING_TIME = 300000; // 5 minutes
    const SILENCE_THRESHOLD = 0.02; // Seuil de silence légèrement plus élevé
    const SILENCE_DURATION = 1500; // 1.5 secondes de silence
    const MIN_SEGMENT_INTERVAL = 2000; // Minimum 2 secondes entre segments
    /** @type {Blob[]} */
    let audioChunks = [];
    let isProcessingSegment = $state(false); // Nouveau: indique qu'un segment est en cours de traitement
    let lastSegmentTime = 0; // Timestamp du dernier segment traité
    let speechDetectedDuration = 0; // Durée totale de parole détectée dans le segment actuel
    let lastSpeechDetection = 0; // Timestamp de la dernière détection de parole

    // Variables pour TTS (Text-to-Speech)
    /** @type {HTMLAudioElement | null} */
    let audioPlayer = null;
    /** @type {string | null} */
    let currentlyPlayingMessageId = $state(null);
    let isLoadingTTS = $state(false);

    // imagePreviewUrl est maintenant une valeur dérivée.
    // Elle retourne l'URL de l'objet ou null.
    const imagePreviewUrl = $derived.by(() => {
        if (selectedImageFile) {
            console.log(
                "[$derived.by] selectedImageFile changed, creating new preview URL for:",
                selectedImageFile.name,
            );
            const newUrl = URL.createObjectURL(selectedImageFile);
            return newUrl;
        }
        console.log(
            "[$derived.by] selectedImageFile is null, returning null for preview URL.",
        );
        return null;
    });

    // Effet pour gérer la révocation de l'URL blob lorsque imagePreviewUrl change
    // ou lorsque le composant est détruit.
    $effect(() => {
        const urlToRevoke = imagePreviewUrl; // On lit la valeur actuelle de la dérivation

        console.log(
            "[$effect for cleanup] Current imagePreviewUrl for potential cleanup:",
            urlToRevoke,
        );

        return () => {
            // Cette fonction de nettoyage est exécutée :
            // 1. Avant la prochaine exécution de cet effet (si imagePreviewUrl change).
            // 2. Lorsque le composant est détruit.
            if (urlToRevoke) {
                console.log(
                    "[$effect cleanup] Revoking old preview URL:",
                    urlToRevoke,
                );
                URL.revokeObjectURL(urlToRevoke);
            } else {
                console.log("[$effect cleanup] No URL to revoke.");
            }
        };
    });

    onMount(async () => {
        await chatState.initializeSessionAndConnect();
        scrollToBottom();
    });

    function scrollToBottom() {
        if (messagesArea && autoScroll) {
            messagesArea.scrollTop = messagesArea.scrollHeight;
        }
    }

    // Scroll automatique quand les messages changent ou quand l'état thinking change
    $effect(() => {
        chatState.messages; // Réagir aux changements de messages
        chatState.isThinking; // Réagir aux changements d'état thinking

        // Petite temporisation pour laisser le DOM se mettre à jour
        setTimeout(() => {
            scrollToBottom();
        }, 10);
    });

    function handleScroll() {
        if (messagesArea) {
            const isScrolledToBottom =
                messagesArea.scrollHeight - messagesArea.clientHeight <=
                messagesArea.scrollTop + 1;
            autoScroll = isScrolledToBottom;
        }
    }

    /** @param {Event & { currentTarget: EventTarget & HTMLFormElement }} event */
    async function handleSubmit(event) {
        event.preventDefault();
        const textToSend = messageInput.trim();

        if (selectedImageFile) {
            const currentImageFile = selectedImageFile;
            const reader = new FileReader();
            reader.onload = (e) => {
                if (
                    e.target &&
                    typeof e.target.result === "string" &&
                    currentImageFile
                ) {
                    const base64Image = e.target.result.split(",")[1];
                    chatState.sendImageMessage(
                        base64Image,
                        currentImageFile.type,
                        textToSend,
                    );
                    messageInput = "";
                    selectedImageFile = null;
                    autoScroll = true;
                }
            };
            reader.onerror = (error) => {
                console.error("Error reading file:", error);
                chatState.addMessage(
                    "Error reading image file.",
                    "error-message",
                );
            };
            reader.readAsDataURL(currentImageFile);
        } else if (textToSend) {
            chatState.sendTextMessage(textToSend);
            messageInput = "";
            autoScroll = true;
        } else {
            console.warn("Attempted to send an empty message.");
            return;
        }
    }

    /** @param {Event} event */
    function handleFileSelect(event) {
        const target = /** @type {HTMLInputElement} */ (event.target);
        if (target.files && target.files[0]) {
            selectedImageFile = target.files[0];
            console.log(
                "[handleFileSelect] New file selected:",
                selectedImageFile,
            );
        } else {
            selectedImageFile = null;
            console.log("[handleFileSelect] File selection cleared");
        }
    }

    function triggerFileInput() {
        fileInput?.click();
    }

    function removeSelectedImage() {
        selectedImageFile = null;
        console.log("[removeSelectedImage] File removed by user");
        if (fileInput) {
            fileInput.value = "";
        }
    }

    // Fonctions pour l'enregistrement audio
    async function startRecording() {
        try {
            // Demander l'accès au micro
            audioStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                },
            });

            // Créer le MediaRecorder
            mediaRecorder = new MediaRecorder(audioStream, {
                mimeType: "audio/webm;codecs=opus",
            });

            // Configurer l'AudioContext pour la détection de silence
            audioContext = new AudioContext({ sampleRate: 16000 });
            const source = audioContext.createMediaStreamSource(audioStream);
            analyser = audioContext.createAnalyser();
            analyser.fftSize = 512;
            source.connect(analyser);

            const bufferLength = analyser.frequencyBinCount;
            dataArray = new Float32Array(bufferLength);

            // Réinitialiser les chunks audio
            audioChunks = [];

            // Configurer les événements du MediaRecorder
            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };

            mediaRecorder.onstop = () => {
                processSegmentAudio();
            };

            // Démarrer l'enregistrement
            mediaRecorder.start(100); // Chunk toutes les 100ms
            isRecording = true;
            recordingStartTime = Date.now();

            // Timeout maximum de 30 secondes
            recordingTimeout = setTimeout(() => {
                stopRecording();
            }, MAX_RECORDING_TIME);

            // Démarrer la détection de silence
            detectSilence();

            console.log("[startRecording] Enregistrement démarré");
        } catch (error) {
            console.error("Erreur d'accès au microphone:", error);
            chatState.addMessage(
                "Erreur : Impossible d'accéder au microphone. Veuillez autoriser l'accès au microphone dans votre navigateur.",
                "error-message",
            );
        }
    }

    function detectSilence() {
        if (!analyser || !dataArray || !isRecording) return;

        analyser.getFloatTimeDomainData(dataArray);

        // Calculer le niveau sonore RMS
        let rms = 0;
        for (let i = 0; i < dataArray.length; i++) {
            rms += dataArray[i] * dataArray[i];
        }
        rms = Math.sqrt(rms / dataArray.length);

        const currentTime = Date.now();

        if (rms < SILENCE_THRESHOLD) {
            // Silence détecté
            if (!silenceTimeout && !isProcessingSegment) {
                silenceTimeout = setTimeout(() => {
                    // Vérifier qu'on a eu au moins 500ms de parole avant de traiter
                    if (speechDetectedDuration >= 500) {
                        console.log(
                            `[detectSilence] Pause détectée avec ${speechDetectedDuration}ms de parole, traitement du segment`,
                        );
                        processCurrentSegment();
                    } else {
                        console.log(
                            `[detectSilence] Pause détectée mais seulement ${speechDetectedDuration}ms de parole, segment ignoré`,
                        );
                        // Réinitialiser pour le prochain segment
                        speechDetectedDuration = 0;
                    }
                }, SILENCE_DURATION);
            }
        } else {
            // Parole détectée
            if (lastSpeechDetection > 0) {
                speechDetectedDuration += currentTime - lastSpeechDetection;
            }
            lastSpeechDetection = currentTime;

            // Son détecté, annuler le timeout de silence
            if (silenceTimeout) {
                clearTimeout(silenceTimeout);
                silenceTimeout = null;
            }
        }

        // Continuer la détection si on enregistre encore
        if (isRecording) {
            requestAnimationFrame(detectSilence);
        }
    }

    function stopRecording() {
        if (!isRecording) return;

        isRecording = false;

        // Nettoyer les timeouts
        if (recordingTimeout) {
            clearTimeout(recordingTimeout);
            recordingTimeout = null;
        }
        if (silenceTimeout) {
            clearTimeout(silenceTimeout);
            silenceTimeout = null;
        }

        // Changer temporairement l'événement onstop pour le traitement final
        if (mediaRecorder && mediaRecorder.state !== "inactive") {
            mediaRecorder.onstop = () => {
                processRecordedAudio(); // Traitement final sans redémarrage
                cleanupAudioResources();
            };
            mediaRecorder.stop();
        } else {
            // Si pas de MediaRecorder actif, nettoyer directement
            cleanupAudioResources();
        }

        console.log("[stopRecording] Enregistrement arrêté");
    }

    function cleanupAudioResources() {
        // Fermer l'AudioContext
        if (audioContext && audioContext.state !== "closed") {
            audioContext.close();
            audioContext = null;
        }

        // Arrêter le flux audio
        if (audioStream) {
            audioStream.getTracks().forEach((track) => track.stop());
            audioStream = null;
        }

        // Nettoyer les références
        analyser = null;
        dataArray = null;
        mediaRecorder = null;
    }

    async function processRecordedAudio() {
        if (audioChunks.length === 0) {
            console.log("[processRecordedAudio] Aucun chunk audio à traiter");
            return;
        }

        // Vérifier s'il y a eu de la parole récente (dans les 3 dernières secondes)
        const now = Date.now();
        const timeSinceLastSpeech = now - lastSpeechDetection;

        if (timeSinceLastSpeech > 3000 || speechDetectedDuration < 300) {
            console.log(
                `[processRecordedAudio] Segment final ignoré - pas de parole récente (${timeSinceLastSpeech}ms depuis dernière parole, ${speechDetectedDuration}ms de parole détectée)`,
            );
            audioChunks = [];
            return;
        }

        // Créer un blob avec tous les chunks
        const audioBlob = new Blob(audioChunks, {
            type: "audio/webm;codecs=opus",
        });

        // Vérifier que le blob a une taille suffisante (au moins 2KB pour le segment final)
        if (audioBlob.size < 2048) {
            console.log(
                `[processRecordedAudio] Segment final trop petit (${audioBlob.size} bytes), ignoré`,
            );
            audioChunks = [];
            return;
        }

        console.log(
            `[processRecordedAudio] Traitement du segment final de ${audioBlob.size} bytes avec ${speechDetectedDuration}ms de parole détectée`,
        );

        // Convertir en ArrayBuffer puis en base64
        const arrayBuffer = await audioBlob.arrayBuffer();
        const uint8Array = new Uint8Array(arrayBuffer);

        // Convertir en base64 par chunks pour éviter l'erreur de pile d'appels
        let binaryString = "";
        const chunkSize = 8192; // Traiter par blocs de 8KB
        for (let i = 0; i < uint8Array.length; i += chunkSize) {
            const chunk = uint8Array.slice(i, i + chunkSize);
            binaryString += String.fromCharCode(...chunk);
        }
        const base64Audio = btoa(binaryString);

        // Envoyer l'audio au serveur
        chatState.sendAudioMessage(base64Audio, "audio/webm;codecs=opus");

        // Nettoyer les chunks
        audioChunks = [];

        console.log("[processRecordedAudio] Audio traité et envoyé");
    }

    async function processCurrentSegment() {
        if (isProcessingSegment) return; // Éviter les traitements multiples

        // Ne pas traiter de nouveaux segments si l'agent est en train de répondre
        if (chatState.isThinking) {
            console.log(
                "[processCurrentSegment] Agent en cours de réponse, segment ignoré",
            );
            // Nettoyer le timeout et ne pas traiter
            if (silenceTimeout) {
                clearTimeout(silenceTimeout);
                silenceTimeout = null;
            }
            return;
        }

        // Vérifier l'intervalle minimum entre segments
        const now = Date.now();
        if (now - lastSegmentTime < MIN_SEGMENT_INTERVAL) {
            console.log(
                `[processCurrentSegment] Segment ignoré - trop proche du précédent (${now - lastSegmentTime}ms)`,
            );
            // Nettoyer le timeout et ne pas traiter
            if (silenceTimeout) {
                clearTimeout(silenceTimeout);
                silenceTimeout = null;
            }
            return;
        }

        console.log("[processCurrentSegment] Début du traitement du segment");

        // Nettoyer le timeout de silence
        if (silenceTimeout) {
            clearTimeout(silenceTimeout);
            silenceTimeout = null;
        }

        isProcessingSegment = true;
        lastSegmentTime = now;

        // Arrêter temporairement le MediaRecorder pour récupérer les données
        if (mediaRecorder && mediaRecorder.state === "recording") {
            mediaRecorder.stop();
        }

        // Le traitement se fera dans l'événement onstop du MediaRecorder
        // qui appellera processSegmentAudio()
    }

    async function processSegmentAudio() {
        console.log(
            "[processSegmentAudio] DÉBUT - audioChunks.length:",
            audioChunks.length,
        );

        if (audioChunks.length === 0) {
            console.log("[processSegmentAudio] Aucun chunk audio à traiter");
            restartRecording();
            return;
        }

        // Créer un blob avec les chunks du segment actuel
        const audioBlob = new Blob(audioChunks, {
            type: "audio/webm;codecs=opus",
        });

        // Vérifier que le blob a une taille suffisante (au moins 1KB)
        if (audioBlob.size < 1024) {
            console.log(
                `[processSegmentAudio] Segment trop petit (${audioBlob.size} bytes), ignoré`,
            );
            // Nettoyer les chunks et redémarrer sans envoyer
            audioChunks = [];
            restartRecording();
            return;
        }

        console.log(
            `[processSegmentAudio] Traitement d'un segment de ${audioBlob.size} bytes avec parole détectée`,
        );

        // Convertir en ArrayBuffer puis en base64
        const arrayBuffer = await audioBlob.arrayBuffer();
        const uint8Array = new Uint8Array(arrayBuffer);

        // Convertir en base64 par chunks pour éviter l'erreur de pile d'appels
        let binaryString = "";
        const chunkSize = 8192; // Traiter par blocs de 8KB
        for (let i = 0; i < uint8Array.length; i += chunkSize) {
            const chunk = uint8Array.slice(i, i + chunkSize);
            binaryString += String.fromCharCode(...chunk);
        }
        const base64Audio = btoa(binaryString);

        console.log("[processSegmentAudio] Envoi au serveur...");

        // Envoyer l'audio au serveur
        chatState.sendAudioMessage(base64Audio, "audio/webm;codecs=opus");

        // Nettoyer les chunks pour le prochain segment
        audioChunks = [];

        console.log("[processSegmentAudio] Appel restartRecording...");

        // Redémarrer l'enregistrement pour le prochain segment
        restartRecording();
    }

    function restartRecording() {
        console.log(
            "[restartRecording] DÉBUT - isRecording:",
            isRecording,
            "isProcessingSegment:",
            isProcessingSegment,
        );

        if (!isRecording) {
            console.log("[restartRecording] ARRÊT - isRecording est false");
            return; // Si l'utilisateur a fermé le micro, ne pas redémarrer
        }

        console.log("[restartRecording] Redémarrage de l'enregistrement...");

        // Redémarrer le MediaRecorder pour le prochain segment
        if (audioStream) {
            try {
                console.log(
                    "[restartRecording] Création nouveau MediaRecorder...",
                );
                mediaRecorder = new MediaRecorder(audioStream, {
                    mimeType: "audio/webm;codecs=opus",
                });

                mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) {
                        audioChunks.push(event.data);
                    }
                };

                mediaRecorder.onstop = () => {
                    console.log(
                        "[restartRecording] MediaRecorder.onstop déclenché",
                    );
                    processSegmentAudio();
                };

                console.log("[restartRecording] Démarrage MediaRecorder...");
                mediaRecorder.start(100); // Chunk toutes les 100ms

                // Remettre isProcessingSegment à false et réinitialiser les compteurs de parole
                console.log(
                    "[restartRecording] Remise à false de isProcessingSegment",
                );
                isProcessingSegment = false;
                speechDetectedDuration = 0;
                lastSpeechDetection = 0;

                console.log(
                    "[restartRecording] SUCCÈS - isProcessingSegment:",
                    isProcessingSegment,
                );
            } catch (error) {
                console.error(
                    "[restartRecording] ERREUR lors du redémarrage:",
                    error,
                );
                isProcessingSegment = false;
                // En cas d'erreur, fermer complètement
                stopRecording();
            }
        } else {
            console.error(
                "[restartRecording] ERREUR - Pas de stream audio disponible",
            );
            isProcessingSegment = false;
            stopRecording();
        }
    }

    function toggleRecording() {
        if (isRecording) {
            stopRecording();
        } else {
            startRecording();
        }
    }

    // Fonctions TTS (Text-to-Speech)
    /**
     * Lit le message de l'agent avec synthèse vocale en streaming depuis le serveur
     * @param {string} messageId - L'ID du message à lire
     * @param {string} messageText - Le texte du message à lire
     */
    async function playMessage(messageId, messageText) {
        try {
            // Si un audio est déjà en cours, l'arrêter
            if (audioPlayer && !audioPlayer.paused) {
                audioPlayer.pause();
                audioPlayer.currentTime = 0;
            }

            // Si c'est le même message, toggle play/pause
            if (currentlyPlayingMessageId === messageId) {
                currentlyPlayingMessageId = null;
                return;
            }

            isLoadingTTS = true;
            currentlyPlayingMessageId = messageId;

            console.log(
                `[TTS] Envoi du texte complet au serveur pour traitement: "${messageText.substring(0, 50)}..."`,
            );

            // Démarrer le streaming depuis le serveur
            await playMessageWithServerStreaming(messageText, messageId);
        } catch (error) {
            console.error("Erreur TTS:", error);
            const errorMessage =
                error instanceof Error ? error.message : "Erreur inconnue";
            chatState.addMessage(
                "Erreur lors de la synthèse vocale: " + errorMessage,
                "error-message",
            );
            currentlyPlayingMessageId = null;
            isLoadingTTS = false;
        }
    }

    /**
     * Joue les segments reçus du serveur en streaming
     * @param {string} messageText - Le texte complet du message
     * @param {string} messageId - L'ID du message original
     */
    async function playMessageWithServerStreaming(messageText, messageId) {
        const httpBaseUrl = PUBLIC_FAST_API_URL;

        try {
            const response = await fetch(`${httpBaseUrl}/tts-stream`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ text: messageText }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const reader = response.body?.getReader();
            if (!reader) {
                throw new Error("Impossible de lire le stream de réponse");
            }

            const decoder = new TextDecoder();
            let buffer = "";
            /** @type {Array<{audioUrl: string, index: number, text: string}>} */
            let audioQueue = [];
            let currentPlayingIndex = 0;
            let isPlayingStarted = false;

            // Fonction pour jouer le prochain segment dans la queue
            async function playNextInQueue() {
                if (currentlyPlayingMessageId !== messageId) {
                    console.log(
                        "[TTS Stream] Lecture arrêtée par l'utilisateur",
                    );
                    return;
                }

                if (currentPlayingIndex < audioQueue.length) {
                    const { audioUrl, text } = audioQueue[currentPlayingIndex];
                    console.log(
                        `[TTS Stream] Lecture du segment ${currentPlayingIndex + 1}: "${text.substring(0, 30)}..."`,
                    );

                    audioPlayer = new Audio(audioUrl);

                    audioPlayer.oncanplay = () => {
                        if (currentPlayingIndex === 0) {
                            isLoadingTTS = false; // Premier segment prêt
                        }
                    };

                    audioPlayer.onended = async () => {
                        URL.revokeObjectURL(audioUrl);
                        currentPlayingIndex++;
                        await playNextInQueue();
                    };

                    audioPlayer.onerror = () => {
                        console.error("Erreur lors de la lecture du segment");
                        URL.revokeObjectURL(audioUrl);
                        currentlyPlayingMessageId = null;
                        isLoadingTTS = false;
                    };

                    await audioPlayer.play();
                } else {
                    // Plus de segments à jouer
                    console.log(
                        "[TTS Stream] Lecture de tous les segments terminée",
                    );
                    currentlyPlayingMessageId = null;
                    isLoadingTTS = false;
                }
            }

            // Lire le stream
            while (true) {
                const { done, value } = await reader.read();

                if (done) {
                    console.log("[TTS Stream] Stream terminé");
                    break;
                }

                buffer += decoder.decode(value, { stream: true });

                // Traiter les lignes complètes dans le buffer
                const lines = buffer.split("\n");
                buffer = lines.pop() || ""; // Garder la ligne incomplète

                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        try {
                            const data = JSON.parse(line.substring(6));

                            if (data.error) {
                                console.error(
                                    `[TTS Stream] Erreur segment ${data.index}:`,
                                    data.error,
                                );
                                continue;
                            }

                            console.log(
                                `[TTS Stream] Segment ${data.index + 1}/${data.total_segments} reçu`,
                            );

                            // Décoder l'audio et créer l'URL
                            const audioBytes = Uint8Array.from(
                                atob(data.audio_data),
                                (c) => c.charCodeAt(0),
                            );
                            const audioBlob = new Blob([audioBytes], {
                                type: "audio/mpeg",
                            });
                            const audioUrl = URL.createObjectURL(audioBlob);

                            // Ajouter à la queue
                            audioQueue[data.index] = {
                                audioUrl,
                                index: data.index,
                                text: data.text,
                            };

                            // Démarrer la lecture du premier segment dès qu'il arrive
                            if (data.index === 0 && !isPlayingStarted) {
                                isPlayingStarted = true;
                                await playNextInQueue();
                            }
                        } catch (parseError) {
                            console.error(
                                "[TTS Stream] Erreur parsing JSON:",
                                parseError,
                            );
                        }
                    }
                }

                // Vérifier si l'utilisateur a arrêté la lecture
                if (currentlyPlayingMessageId !== messageId) {
                    reader.cancel();
                    break;
                }
            }
        } catch (error) {
            console.error("Erreur lors du streaming TTS:", error);
            currentlyPlayingMessageId = null;
            isLoadingTTS = false;
            throw error;
        }
    }

    /**
     * Arrête la lecture audio en cours
     */
    function stopPlayback() {
        if (audioPlayer && !audioPlayer.paused) {
            audioPlayer.pause();
            audioPlayer.currentTime = 0;
        }
        currentlyPlayingMessageId = null;
        isLoadingTTS = false;
    }
</script>

<svelte:head>
    <title>Agency Flow</title>
</svelte:head>

<div class="w-full">
    <div
        class="font-sans relative m-5 mb-0 flex flex-col h-[calc(100vh-118px)] max-w-full px-10 mx-auto"
    >
        <div
            class="absolute inset-0 bg-white/50 backdrop-blur-xl z-[-1] rounded-2xl"
        ></div>
        <h1
            class="text-center text-gray-800 py-4
        mt-0 text-xl font-semibold"
        >
            Agency Flow
        </h1>
        <div
            bind:this={messagesArea}
            class="flex-grow overflow-y-auto overflow-x-hidden p-4 mx-4 mb-4"
            onscroll={handleScroll}
        >
            {#if chatState.showWelcomeMessage}
                <!-- Message de bienvenue -->
                <div
                    class="flex flex-col items-center justify-center h-full text-center"
                >
                    <div class="max-w-md mx-auto">
                        <h2 class="text-3xl font-bold text-gray-800 mb-4">
                            Bienvenue sur Agency Flow !
                        </h2>
                        <p class="text-lg text-gray-600 mb-6 leading-relaxed">
                            Votre assistant IA intelligent est prêt à vous
                            aider. Pour commencer une nouvelle conversation,
                            créez une session ou sélectionnez une session
                            existante dans la barre latérale.
                        </p>
                        <div class="mb-4">
                            <button
                                class="bg-blue-600 cursor-pointer hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors duration-200 shadow-md"
                                onclick={() => createNewSession(USER_ID)}
                            >
                                Créer une nouvelle session
                            </button>
                        </div>
                        <p class="text-sm text-gray-500">
                            Vous pouvez également partager des images et
                            recevoir des réponses personnalisées.
                        </p>
                    </div>
                </div>
            {:else}
                <!-- Messages normaux -->
                {#each chatState.messages as message (message.id)}
                    <div
                        class="chat_message mb-2.5 p-2.5 rounded-2xl break-words leading-normal flex flex-col {message.type ===
                            'user-message' || message.type === 'user-image'
                            ? 'bg-blue-600 text-white w-fit max-w-[80vw] overflow-x-auto ml-auto rounded-br-md'
                            : ''} {message.type === 'agent-message'
                            ? 'bg-white text-gray-800 w-fit max-w-[80vw] overflow-x-auto mr-auto rounded-bl-md'
                            : ''} {message.type === 'system-message'
                            ? 'italic text-white text-center text-sm py-1'
                            : ''} {message.type === 'error-message'
                            ? 'bg-red-100 text-red-700 border border-red-300 font-bold rounded-md'
                            : ''}"
                        data-event-id={message.id}
                    >
                        {#if message.type === "user-image" && message.imageDataUrl}
                            <img
                                src={message.imageDataUrl}
                                alt="User upload"
                                class="max-w-full max-h-52 rounded-lg mb-1.5"
                            />
                        {/if}
                        {#if message.type === "agent-message"}
                            <div class="flex items-start gap-2">
                                <div class="flex-grow">
                                    {@html parseMarkdown(message.text)}
                                </div>
                                <button
                                    onclick={() =>
                                        playMessage(
                                            String(message.id),
                                            message.text,
                                        )}
                                    class="flex-shrink-0 mt-1 p-1 rounded-full hover:bg-gray-100 transition-colors duration-200"
                                    title={currentlyPlayingMessageId ===
                                    message.id
                                        ? "Arrêter la lecture"
                                        : isLoadingTTS
                                          ? "Chargement..."
                                          : "Écouter ce message"}
                                    disabled={isLoadingTTS &&
                                        currentlyPlayingMessageId !==
                                            message.id}
                                >
                                    <span class="text-lg">
                                        {#if isLoadingTTS && currentlyPlayingMessageId === message.id}
                                            🔄
                                        {:else if currentlyPlayingMessageId === message.id}
                                            🔊
                                        {:else}
                                            🔉
                                        {/if}
                                    </span>
                                </button>
                            </div>
                        {:else}
                            {@html message.text}
                        {/if}
                    </div>
                {/each}

                <!-- Animation de thinking quand l'agent réfléchit -->
                {#if chatState.isThinking && !chatState.showWelcomeMessage}
                    <div class="thinking-dots mx-auto text-white w-fit mb-4">
                        <span class="dot"></span>
                        <span class="dot"></span>
                        <span class="dot"></span>
                    </div>
                {/if}
            {/if}
        </div>

        {#if imagePreviewUrl}
            <div class="px-4 pb-2.5 flex items-center relative">
                <img
                    src={imagePreviewUrl}
                    alt="Selected preview"
                    class="max-w-[100px] max-h-[100px] rounded-md border border-gray-300"
                />
                <button
                    onclick={removeSelectedImage}
                    class="absolute top-[-5px] left-[85px] bg-black/50 text-white border-none rounded-full w-5 h-5 text-xs leading-[18px] text-center cursor-pointer p-0 hover:bg-black/70"
                >
                    &times;
                </button>
            </div>
        {/if}
    </div>
    <div class="py-4">
        <form
            onsubmit={handleSubmit}
            class="flex items-center py-1 px-4 max-w-2xl mx-auto my-2 border border-gray-300 rounded-full"
        >
            <button
                type="button"
                onclick={triggerFileInput}
                class="mr-2.5 relative -top-1 cursor-pointer text-lgdisabled:cursor-not-allowed disabled:text-gray-500"
                title="Attach image"
                disabled={!chatState.isConnected}
            >
                <span class="text-5xl text-white">+</span>
            </button>
            <button
                type="button"
                onclick={toggleRecording}
                class="mr-2.5 relative -top-1 cursor-pointer text-lg disabled:cursor-not-allowed disabled:text-gray-500"
                title={isRecording
                    ? isProcessingSegment
                        ? "Traitement en cours... (cliquez pour arrêter)"
                        : "Écoute continue - Parlez librement (cliquez pour arrêter)"
                    : "Enregistrer un message vocal"}
                disabled={!chatState.isConnected}
            >
                <span
                    class="text-4xl {isRecording
                        ? isProcessingSegment
                            ? 'text-orange-500'
                            : 'text-red-500 animate-pulse'
                        : 'text-white'}"
                >
                    {isRecording ? (isProcessingSegment ? "🟠" : "🔴") : "🎤"}
                </span>
            </button>
            <input
                type="file"
                bind:this={fileInput}
                onchange={handleFileSelect}
                accept="image/png, image/jpeg, image/gif, image/webp"
                class="hidden"
            />
            <input
                type="text"
                name="message"
                bind:value={messageInput}
                autocomplete="off"
                placeholder="Écrivez votre message ou ajoutez une image..."
                class="flex-grow p-3 mr-2.5text-base outline-none focus:outline-none text-white cursor-text"
                disabled={!chatState.isConnected}
            />
            <button
                type="submit"
                class="py-3 px-5 border-none font-black text-xl text-white rounded-full cursor-pointer transition-colors duration-200 ease-in-out disabled:cursor-not-allowed"
                disabled={!chatState.isConnected ||
                    (!messageInput.trim() && !selectedImageFile)}
            >
                Envoyer
            </button>
        </form>
    </div>
</div>
