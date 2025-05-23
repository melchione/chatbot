// import { writable } from 'svelte/store'; // Commentaire supprimé
import { PUBLIC_FAST_API_URL, PUBLIC_FAST_API_WS_URL } from '$env/static/public';

const USER_ID = "test_user"; // User ID fixe pour le moment

/**
 * @typedef {{
 *   id: string | number,
 *   text: string, // Pour les messages texte ou le prompt de l\'image
 *   type: string, // \'user-message\', \'agent-message\', \'system-message\', \'user-image\'
 *   completed?: boolean,
 *   imageDataUrl?: string | null, // Data URL pour les images envoyées par l\'utilisateur
 *   mimeType?: string | null // Ajout pour spécifier le type MIME de l\'image
 * }} Message
 */

/**
 * @typedef {{
 *  session_id: string;
 *  user_id: string;
 *  app_name: string;
 *  last_update_time: number;
 * }} UserSession
 */

class ChatState {
    /** @type {Array<Message>} */
    _messages = $state([]);
    _isConnected = $state(false);
    /** @type {string | null} */
    _currentSessionId = $state(null);
    /** @type {WebSocket | null} */
    _ws = null;
    _isThinking = $state(false);
    /** @type {Array<UserSession>} */
    _userSessions = $state([]);
    _isSwitchingSession = $state(false); // Pour éviter la reconnexion auto pendant un switch manuel
    _showWelcomeMessage = $state(false); // Pour afficher le message de bienvenue
    _messageIdCounter = 0; // Compteur pour générer des IDs uniques

    constructor() {
        // Initialisation si nécessaire, ou laisser vide si $state gère l'initialisation
    }

    // Méthode pour générer un ID unique
    _generateUniqueId() {
        this._messageIdCounter++;
        return `msg_${Date.now()}_${this._messageIdCounter}_${Math.random().toString(36).substr(2, 9)}`;
    }

    // Getters pour l'accès en lecture seule de l'extérieur si nécessaire
    // (Svelte 5 runes rendent souvent cela implicite via la réactivité de $state)
    get messages() {
        return this._messages;
    }

    get isThinking() {
        return this._isThinking;
    }

    get isConnected() {
        return this._isConnected;
    }

    get currentSessionId() {
        return this._currentSessionId;
    }

    get userSessions() {
        return this._userSessions;
    }

    get showWelcomeMessage() {
        return this._showWelcomeMessage;
    }

    // Méthodes pour modifier l'état
    /**
     * @param {string} text - Le contenu textuel du message (ou prompt pour une image)
     * @param {string} type - Le type de message (e.g., \'user-message\', \'agent-message\', \'user-image\')
     * @param {(string | number | null)} [eventId=null]
     * @param {(string | null)} [imageDataUrl=null]
     * @param {(string | null)} [mimeType=null]
     */
    addMessage(text, type, eventId = null, imageDataUrl = null, mimeType = null) {
        if (eventId && this._messages.some(msg => msg.id === eventId)) {
            return;
        }
        const newMessage = {
            text,
            type,
            id: eventId || this._generateUniqueId(),
            imageDataUrl,
            mimeType
        };
        this._messages = [...this._messages, newMessage];
    }

    /**
     * @param {string} text
     */
    updateLastMessagePart(text) {
        this._isThinking = false;
        if (this._messages.length > 0) {
            let lastMessage = this._messages[this._messages.length - 1];
            if (lastMessage && lastMessage.type === "agent-message" && !lastMessage.completed) {
                const updatedText = lastMessage.text + text;
                this._messages = [
                    ...this._messages.slice(0, -1),
                    { ...lastMessage, text: updatedText }
                ];
            } else {
                // Si le dernier message n\'est pas un message agent en cours, ou s\'il est complété,
                // on ajoute un nouveau message agent.
                this.addMessage(text, "agent-message");
            }
        } else {
            // Si aucun message n'existe, créer le premier message
            this.addMessage(text, "agent-message");
        }
    }

    completeLastMessage() {
        this._isThinking = false;
        if (this._messages.length > 0) {
            let lastMessage = this._messages[this._messages.length - 1];
            if (lastMessage && lastMessage.type === "agent-message" && !lastMessage.completed) {
                this._messages = [
                    ...this._messages.slice(0, -1),
                    { ...lastMessage, completed: true }
                ];
            }
        }
    }

    clearMessages() {
        this._messages = [];
    }

    /**
     * @param {boolean} status
     */
    setConnected(status) {
        this._isConnected = status;
    }

    /**
     * @param {string | null} sessionId
     */
    setCurrentSessionId(sessionId) {
        this._currentSessionId = sessionId;
    }

    /**
     * @param {string} userId
     * @param {string} sessionId
     */
    async loadChatHistory(userId, sessionId) {
        // Nettoyer d'abord les messages existants pour éviter les doublons
        this.clearMessages();
        this.addMessage("Loading chat history...", "system-message", "loading-history");

        try {
            const httpBaseUrl = PUBLIC_FAST_API_URL;
            const historyUrl = `${httpBaseUrl}/session_history/${userId}/${sessionId}`;
            const response = await fetch(historyUrl);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: "Failed to fetch history, server returned: " + response.status }));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            if (data.events && data.events.length > 0) {
                // Supprimer le message de loading
                this._messages = this._messages.filter(msg => msg.id !== "loading-history");

                const historyMessages = data.events.map(/** @param {any} event */ event => {
                    let textContent = "";
                    let imageDataUrl = null;
                    let mimeType = null;
                    let messageType = event.author === 'user' ? "user-message" : "agent-message";

                    if (event.content && event.content.parts && event.content.parts.length > 0) {
                        event.content.parts.forEach(
                            /** @param {any} part */
                            part => {
                                if (part.text) {
                                    textContent += part.text;
                                }
                                if (part.inlineData && part.inlineData.data && part.inlineData.mimeType) {
                                    imageDataUrl = `data:${part.inlineData.mimeType};base64,${part.inlineData.data}`;
                                    mimeType = part.inlineData.mimeType;
                                    if (event.author === 'user') {
                                        messageType = "user-image";
                                    }
                                }
                            });
                    }

                    if (textContent || imageDataUrl) { // On ajoute seulement s'il y a du contenu
                        // Utiliser l'ID de l'événement du serveur s'il existe, sinon générer un ID unique
                        const messageId = event.id || `history_${this._generateUniqueId()}`;
                        return {
                            text: textContent,
                            type: messageType,
                            id: messageId,
                            imageDataUrl: imageDataUrl,
                            mimeType: mimeType
                        };
                    }
                    return null;
                }).filter(
                    /**
                    * @param {(Message | null)} m
                    * @returns {m is Message}
                    */
                    m => m !== null
                );

                // S'assurer qu'il n'y a pas de doublons d'ID
                const uniqueHistoryMessages = historyMessages.filter((/** @type {Message} */ message, /** @type {number} */ index, /** @type {Message[]} */ array) =>
                    array.findIndex((/** @type {Message} */ m) => m.id === message.id) === index
                );

                this._messages = [...uniqueHistoryMessages];
                this.addMessage("Chat history loaded.", "system-message", "history-loaded");
            } else {
                // Supprimer le message de loading
                this._messages = this._messages.filter(msg => msg.id !== "loading-history");
                this.addMessage("No previous chat history found or session is new.", "system-message", "no-history");
            }
        } catch (error) {
            console.error("Error loading chat history:", error);
            // Supprimer le message de loading
            this._messages = this._messages.filter(msg => msg.id !== "loading-history");
            if (error instanceof Error) {
                this.addMessage("Error loading chat history: " + error.message, "error-message", "history-error");
            } else {
                this.addMessage("An unknown error occurred while loading chat history.", "error-message", "history-error-unknown");
            }
        }
    }

    /**
     * @param {string} userId
     * @param {string} sessionId
     */
    connectToChatWebSocket(userId, sessionId) {
        if (!sessionId) {
            this.addMessage("Error: No session ID available to connect to chat.", "error-message");
            this.setConnected(false);
            return;
        }
        const chatWsUrl = `${PUBLIC_FAST_API_WS_URL}/ws/${userId}/${sessionId}`;
        this._ws = new WebSocket(chatWsUrl);

        this._ws.onopen = () => {
            console.log("Connected to WebSocket server with User ID:", userId, "and Session ID:", sessionId);
            this.setConnected(true);
            this.addMessage("Connected to agent.", "system-message", "connected-to-agent");
            this._isSwitchingSession = false; // Réinitialiser après une connexion réussie
        };

        this._ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log("Received:", data);
            if (data.type === "status" && data.message === "Agent service connected") {
                this._isThinking = false;
            }
            if (data.type === "message_part" && data.text) {
                this.updateLastMessagePart(data.text);
            } else if (data.type === "message_end") {
                this.completeLastMessage();
            } else if (data.type === "transcription" && data.text) {
                // Afficher la transcription comme un message utilisateur
                const transcriptionId = `transcription_${this._generateUniqueId()}`;
                this.addMessage(data.text, "user-message", transcriptionId);
            } else if (data.type === "error" && data.message) {
                const errorId = data.id || `error_${this._generateUniqueId()}`;
                this.addMessage("Error: " + data.message, "error-message", errorId);
                this._isThinking = false;
            } else if (data.text) {
                const messageId = data.id || `ws_${this._generateUniqueId()}`;
                this.addMessage(data.text, "agent-message", messageId);
            }
        };

        this._ws.onclose = () => {
            console.log("Disconnected from WebSocket server.");
            this.setConnected(false);
            // Uniquement tenter de reconnecter si ce n'est pas un changement de session manuel
            if (!this._isSwitchingSession) {
                this.addMessage("Disconnected. Attempting to reconnect in 5 seconds...", "system-message", "reconnecting-msg");
                setTimeout(() => this.initializeSessionAndConnect(null, true), 5000);
            } else {
                console.log("WebSocket closed due to session switch. No auto-reconnect.");
                // this._isSwitchingSession sera remis à false par la méthode appelante (createNewSession/switchSession) après la nouvelle connexion
            }
        };

        this._ws.onerror = (error) => {
            console.error("WebSocket error:", error);
            this.addMessage("WebSocket error. Check console.", "error-message", "ws-error");
            this._isThinking = false;
            if (this._ws) this._ws.close();
        };
    }

    /**
     * @param {string | null} [initialSessionIdFromLoad=null]
     * @param {boolean} [isReconnectAttempt=false]
     */
    async initializeSessionAndConnect(initialSessionIdFromLoad = null, isReconnectAttempt = false) {
        this.setConnected(false);
        if (!isReconnectAttempt) {
            this.addMessage("Initializing session...", "system-message", "initializing-session");
        } else {
            // Si c'est une tentative de reconnexion, ne pas afficher "Initializing session..." à nouveau
            // mais s'assurer que isSwitchingSession est false pour permettre la reconnexion
            this._isSwitchingSession = false;
        }

        let sessionId = initialSessionIdFromLoad;

        if (!sessionId) {
            sessionId = getCookie("chat_session_id");
        }

        // Charger les sessions utilisateur au démarrage ou lors du changement de session
        // On le fait ici car USER_ID est disponible
        await this.loadUserSessions(USER_ID);

        if (sessionId) {
            this._showWelcomeMessage = false;
            this.setCurrentSessionId(sessionId);
            // Ne pas charger l\'historique ici si c\'est une tentative de reconnexion après une déconnexion
            // L\'historique est déjà chargé ou sera géré différemment
            if (!isReconnectAttempt) {
                this.addMessage("Using existing session: " + sessionId, "system-message");
                await this.loadChatHistory(USER_ID, sessionId);
            }
            this.connectToChatWebSocket(USER_ID, sessionId);
        } else {
            // Vérifier s'il y a des sessions disponibles
            if (this._userSessions && this._userSessions.length > 0) {
                // Il y a des sessions disponibles, mais aucune n'est sélectionnée
                // On affiche le message de bienvenue et on laisse l'utilisateur choisir
                console.log("Sessions available but no session selected. Showing welcome message.");
                this._showWelcomeMessage = true;
                this.clearMessages();
                this.setConnected(false);
            } else {
                // Aucune session disponible, afficher le message de bienvenue
                console.log("No sessions available. Showing welcome message.");
                this._showWelcomeMessage = true;
                this.clearMessages();
                this.setConnected(false);
            }
        }
    }

    /**
     * @param {string} messageText
     */
    sendTextMessage(messageText) {
        if (messageText && this._ws && this._ws.readyState === WebSocket.OPEN) {
            this._isThinking = true;
            const payload = {
                type: "text",
                data: messageText
            };
            this._ws.send(JSON.stringify(payload));
            this.addMessage(messageText, "user-message");
        } else {
            this.addMessage("Cannot send message. WebSocket not connected or message is empty.", "error-message");
        }
    }

    /**
     * @param {string} imageDataBase64 - L\'image encodée en base64 (sans le préfixe data:mime/type;base64,)
     * @param {string} mimeType - Le type MIME de l\'image (par exemple, \'image/png\', \'image/jpeg\')
     * @param {string} [prompt=""] - Le prompt textuel accompagnant l\'image
     */
    sendImageMessage(imageDataBase64, mimeType, prompt = "") {
        if (imageDataBase64 && mimeType && this._ws && this._ws.readyState === WebSocket.OPEN) {
            this._isThinking = true;
            const payload = {
                type: "image",
                data: imageDataBase64, // Le backend attend la data base64 brute
                mime_type: mimeType,
                prompt: prompt
            };
            this._ws.send(JSON.stringify(payload));
            // Ajoute l\'image et le prompt au store local pour affichage immédiat
            // Le texte du message sera le prompt, et imageDataUrl contiendra l\'image pour l\'affichage local
            this.addMessage(prompt, "user-image", null, `data:${mimeType};base64,${imageDataBase64}`, mimeType);
        } else {
            this.addMessage("Cannot send image. WebSocket not connected, image data or mime type missing.", "error-message");
        }
    }

    /**
     * @param {string} audioDataBase64 - L\'audio encodé en base64
     * @param {string} mimeType - Le type MIME de l\'audio (par exemple, \'audio/webm;codecs=opus\')
     */
    sendAudioMessage(audioDataBase64, mimeType) {
        if (audioDataBase64 && mimeType && this._ws && this._ws.readyState === WebSocket.OPEN) {
            this._isThinking = true;
            const payload = {
                type: "audio",
                data: audioDataBase64,
                mime_type: mimeType
            };
            this._ws.send(JSON.stringify(payload));
            // La transcription sera reçue et affichée via WebSocket
        } else {
            this.addMessage("Cannot send audio. WebSocket not connected, audio data or mime type missing.", "error-message");
        }
    }

    /**
     * @param {string} userId
     */
    async loadUserSessions(userId) {
        console.log("Loading user sessions for", userId);
        try {
            const httpBaseUrl = PUBLIC_FAST_API_URL;
            const sessionsUrl = `${httpBaseUrl}/sessions/${userId}`;
            const response = await fetch(sessionsUrl);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: "Failed to fetch user sessions, server returned: " + response.status }));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            if (data.sessions) {
                // Tri des sessions par last_update_time, du plus récent au plus ancien
                // S'assurer que last_update_time est bien un nombre pour le tri
                this._userSessions = data.sessions.sort((/** @type {UserSession} */ a, /** @type {UserSession} */ b) => {
                    const timeA = a.last_update_time || 0;
                    const timeB = b.last_update_time || 0;
                    return timeB - timeA;
                });
                console.log("User sessions loaded and sorted:", this._userSessions);
            }
        } catch (error) {
            console.error("Error loading user sessions:", error);
            if (error instanceof Error) {
                this.addMessage("Error loading user sessions: " + error.message, "error-message");
            } else {
                this.addMessage("An unknown error occurred while loading user sessions.", "error-message");
            }
        }
    }

    /**
     * Crée une nouvelle session pour l'utilisateur actuel.
     * @param {string} userId - L'ID de l'utilisateur.
     */
    async createNewSession(userId) {
        this.clearMessages();
        this.addMessage("Creating new session...", "system-message");

        this._isSwitchingSession = true; // Indiquer un changement manuel
        this._showWelcomeMessage = false; // Masquer le message de bienvenue

        if (this._ws && this._ws.readyState === WebSocket.OPEN) {
            this._ws.close();
        }
        this.setConnected(false); // Mettre à jour l'état de connexion immédiatement

        removeCookie("chat_session_id");
        this.setCurrentSessionId(null);

        // Créer une nouvelle session via WebSocket
        try {
            const createSessionWsUrl = `${PUBLIC_FAST_API_WS_URL}/ws/create_session/${userId}`;
            const sessionWs = new WebSocket(createSessionWsUrl);

            sessionWs.onopen = () => {
                console.log("Connected to create_session endpoint.");
            };

            sessionWs.onmessage = async (event) => {
                const data = JSON.parse(event.data);
                if (data.type === "session_created" && data.session_id) {
                    const sessionId = data.session_id;
                    if (sessionId) {
                        setCookie("chat_session_id", sessionId);
                    }
                    this.setCurrentSessionId(sessionId);
                    console.log("New session ID received and stored:", sessionId);
                    this.addMessage("Session created: " + sessionId, "system-message");
                    sessionWs.close();
                    if (sessionId) {
                        // Lancer le chargement de l'historique après avoir obtenu un nouveau session_id
                        this.clearMessages(); // Vider les messages précédents
                        this.addMessage("New session created: " + sessionId, "system-message");
                        await this.loadChatHistory(userId, sessionId);
                        this.connectToChatWebSocket(userId, sessionId);
                        await this.loadUserSessions(userId); // Recharger la liste des sessions
                    }
                } else {
                    console.error("Failed to create session:", data);
                    this.addMessage("Error: Could not create session. " + (data.message || ""), "error-message");
                }
            };

            sessionWs.onerror = (error) => {
                console.error("WebSocket error during session creation:", error);
                this.addMessage("Error: Could not connect to create session. Check console.", "error-message");
                this.setConnected(false);
            };

            sessionWs.onclose = () => {
                console.log("Session creation WebSocket closed.");
            };

        } catch (error) {
            console.error("Failed to connect to session creation endpoint:", error);
            if (error instanceof Error) {
                this.addMessage("Fatal error: Could not initiate session creation. " + error.message, "error-message");
            } else {
                this.addMessage("Fatal error: Could not initiate session creation. Check console.", "error-message");
            }
        }
    }

    /**
     * Change la session active pour l'utilisateur.
     * @param {string} userId - L'ID de l'utilisateur.
     * @param {string} newSessionId - L'ID de la nouvelle session à charger.
     */
    async switchSession(userId, newSessionId) {
        if (this._currentSessionId === newSessionId) {
            console.log("Already in session:", newSessionId);
            return;
        }
        this.clearMessages();
        this.addMessage(`Switching to session ${newSessionId}...`, "system-message");
        this._isSwitchingSession = true;

        if (this._ws && this._ws.readyState === WebSocket.OPEN) {
            this._ws.close(); // Fermer la connexion WebSocket actuelle
        }
        this.setConnected(false); // Mettre à jour l'état de connexion immédiatement

        setCookie("chat_session_id", newSessionId);
        this.setCurrentSessionId(newSessionId);

        await this.loadChatHistory(userId, newSessionId);
        this.connectToChatWebSocket(userId, newSessionId);
        // Pas besoin de recharger les sessions utilisateur ici car la liste ne change pas, juste la session active
        // isSwitchingSession sera remis à false par onopen ou onerror de la nouvelle connexion WebSocket
    }

    /**
     * Supprime une session pour l'utilisateur actuel.
     * @param {string} userId - L'ID de l'utilisateur.
     * @param {string} sessionIdToDelete - L'ID de la session à supprimer.
     */
    async deleteSession(userId, sessionIdToDelete) {
        console.log(`Attempting to delete session ${sessionIdToDelete} for user ${userId}`);
        this.addMessage(`Deleting session ${sessionIdToDelete.substring(0, 8)}...`, "system-message");

        try {
            const httpBaseUrl = PUBLIC_FAST_API_URL;
            const deleteUrl = `${httpBaseUrl}/sessions/${userId}/${sessionIdToDelete}`;
            const response = await fetch(deleteUrl, { method: 'DELETE' });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: "Failed to delete session, server returned: " + response.status }));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            this.addMessage(result.message || `Session ${sessionIdToDelete.substring(0, 8)} deleted.`, "system-message");

            // Mettre à jour l'état local
            const oldSessions = [...this._userSessions];
            const deletedSessionIndex = oldSessions.findIndex(session => session.session_id === sessionIdToDelete);
            this._userSessions = this._userSessions.filter(session => session.session_id !== sessionIdToDelete);

            if (this._currentSessionId === sessionIdToDelete) {
                if (this._ws && this._ws.readyState === WebSocket.OPEN) {
                    this._isSwitchingSession = true; // Pour éviter la reconnexion auto pendant la fermeture
                    this._ws.close();
                }
                this.clearMessages();
                removeCookie("chat_session_id");
                this.setCurrentSessionId(null);
                this.setConnected(false);

                if (this._userSessions.length > 0) {
                    // S'il reste des sessions, sélectionner la suivante ou la précédente si la dernière a été supprimée
                    let nextSessionIndex = deletedSessionIndex;
                    if (nextSessionIndex >= this._userSessions.length) { // Si la dernière a été supprimée
                        nextSessionIndex = this._userSessions.length - 1;
                    }
                    this.addMessage("Current session deleted. Switching to another session...", "system-message");
                    // Délai pour s'assurer que l'état du WS est bien géré avant de switcher
                    setTimeout(async () => {
                        await this.switchSession(userId, this._userSessions[nextSessionIndex].session_id);
                    }, 100);
                } else {
                    this.addMessage("Current session deleted. No other sessions available. Please create a new session.", "system-message");
                    // Optionnel: initier la création d'une nouvelle session s'il n'en reste plus
                    // setTimeout(async () => { await this.createNewSession(userId); }, 100);
                }
            }

        } catch (error) {
            console.error("Error deleting session:", error);
            if (error instanceof Error) {
                this.addMessage("Error deleting session: " + error.message, "error-message");
            } else {
                this.addMessage("An unknown error occurred while deleting the session.", "error-message");
            }
        }
    }
}

export const chatState = new ChatState();

// Fonctions utilitaires (getCookie, setCookie) restent en dehors de la classe car elles sont plus générales.
/**
 * @param {string} name
 * @returns {string | null}
 */
function getCookie(name) {
    if (typeof document === 'undefined') return null; // Garde-fou pour SSR
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) {
        const popped = parts.pop();
        return popped ? popped.split(';').shift() || null : null;
    }
    return null;
}

/**
 * @param {string} name
 * @param {string} value
 * @param {number} [days=7]
 */
function setCookie(name, value, days = 7) {
    if (typeof document === 'undefined') return; // Garde-fou pour SSR
    let expires = "";
    if (days) {
        const date = new Date();
        date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
        expires = "; expires=" + date.toUTCString();
    }
    document.cookie = name + "=" + (value || "") + expires + "; path=/";
}

// Pour la compatibilité avec les imports existants
/**
 * @param {string | null} [initialSessionIdFromLoad=null]
 * @param {boolean} [isReconnectAttempt=false]
 */
export const initializeSessionAndConnect = (initialSessionIdFromLoad = null, isReconnectAttempt = false) =>
    chatState.initializeSessionAndConnect(initialSessionIdFromLoad, isReconnectAttempt);

// Pour la compatibilité avec les imports existants
/** @deprecated Utilisez sendTextMessage ou sendImageMessage */
export const sendMessage = (/** @type {string} */ messageText) => chatState.sendTextMessage(messageText);

export const sendTextMessage = (/** @type {string} */ messageText) => chatState.sendTextMessage(messageText);
export const sendImageMessage = (
    /** @type {string} */ imageDataBase64,
    /** @type {string} */ mimeType,
    /** @type {string | undefined} */ prompt
) => chatState.sendImageMessage(imageDataBase64, mimeType, prompt);
export const sendAudioMessage = (
    /** @type {string} */ audioDataBase64,
    /** @type {string} */ mimeType
) => chatState.sendAudioMessage(audioDataBase64, mimeType);

/**
 * Crée une nouvelle session pour l'utilisateur actuel.
 * @param {string} userId - L'ID de l'utilisateur.
 */
export async function createNewSession(userId) {
    await chatState.createNewSession(userId);
}

/**
 * Change la session active pour l'utilisateur.
 * @param {string} userId - L'ID de l'utilisateur.
 * @param {string} newSessionId - L'ID de la nouvelle session à charger.
 */
export async function switchSession(userId, newSessionId) {
    await chatState.switchSession(userId, newSessionId);
}

/**
 * Supprime la session spécifiée pour l'utilisateur.
 * @param {string} userId - L'ID de l'utilisateur.
 * @param {string} sessionId - L'ID de la session à supprimer.
 */
export async function deleteSelectedSession(userId, sessionId) {
    await chatState.deleteSession(userId, sessionId);
}

export function getMessages() {
    return chatState.messages;
}
export function getIsConnected() {
    return chatState.isConnected;
}
export function getCurrentSessionId() {
    return chatState.currentSessionId;
}
export function getIsThinking() {
    return chatState.isThinking;
}
export function getUserSessions() {
    return chatState.userSessions;
}
export function getShowWelcomeMessage() {
    return chatState.showWelcomeMessage;
}

// Fonction utilitaire pour supprimer un cookie
/**
 * @param {string} name
 */
function removeCookie(name) {
    if (typeof document === 'undefined') return; // Garde-fou pour SSR
    document.cookie = name + '=; Path=/; Expires=Thu, 01 Jan 1970 00:00:01 GMT;';
}
