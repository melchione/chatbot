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

    constructor() {
        // Initialisation si nécessaire, ou laisser vide si $state gère l'initialisation
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
            id: eventId || Date.now() + Math.random().toString(36),
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
                const updatedText = lastMessage.text + text.replace(/\n/g, "<br>");
                this._messages = [
                    ...this._messages.slice(0, -1),
                    { ...lastMessage, text: updatedText }
                ];
            } else {
                // Si le dernier message n\'est pas un message agent en cours, ou s\'il est complété,
                // on ajoute un nouveau message agent.
                this.addMessage(text.replace(/\n/g, "<br>"), "agent-message");
            }
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
        this.addMessage("Loading chat history...", "system-message");
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
                const filteredCurrentMessages = this._messages.filter(msg => !(msg.text === "Loading chat history..." && msg.type === "system-message"));

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
                                    textContent += part.text.replace(/\n/g, "<br>");
                                }
                                if (part.inlineData && part.inlineData.data && part.inlineData.mimeType) {
                                    imageDataUrl = `data:${part.inlineData.mimeType};base64,${part.inlineData.data}`;
                                    mimeType = part.inlineData.mimeType;
                                    if (event.author === 'user') {
                                        messageType = "user-image";
                                    } else {
                                        // Si vous voulez différencier les images de l'agent:
                                        // messageType = "agent-image"; 
                                        // Sinon, gardez "agent-message" et l'image s'affichera avec le texte.
                                        // Pour l'instant, si l'agent envoie une image, on la traite comme une partie d'un message agent normal
                                        // et l'image sera affichée par la logique du composant svelte si imageDataUrl est présent.
                                        // La classe CSS pourrait avoir besoin d'ajustement pour les images de l'agent.
                                    }
                                }
                            });
                    }

                    if (textContent || imageDataUrl) { // On ajoute seulement s'il y a du contenu
                        return {
                            text: textContent,
                            type: messageType,
                            id: event.id,
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
                this._messages = [...filteredCurrentMessages, ...historyMessages];
                this.addMessage("Chat history loaded.", "system-message");
            } else {
                this.addMessage("No previous chat history found or session is new.", "system-message");
            }
        } catch (error) {
            console.error("Error loading chat history:", error);
            if (error instanceof Error) {
                this.addMessage("Error loading chat history: " + error.message, "error-message");
            } else {
                this.addMessage("An unknown error occurred while loading chat history.", "error-message");
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
            this.addMessage("Connected to agent.", "system-message");
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
            } else if (data.type === "error" && data.message) {
                this.addMessage("Error: " + data.message, "error-message");
                this._isThinking = false;
            } else if (data.text) {
                this.addMessage(data.text, "agent-message");
            }
        };

        this._ws.onclose = () => {
            console.log("Disconnected from WebSocket server.");
            this.setConnected(false);
            // Uniquement tenter de reconnecter si ce n'est pas un changement de session manuel
            if (!this._isSwitchingSession) {
                this.addMessage("Disconnected. Attempting to reconnect in 5 seconds...", "system-message");
                setTimeout(() => this.initializeSessionAndConnect(null, true), 5000);
            } else {
                console.log("WebSocket closed due to session switch. No auto-reconnect.");
                // this._isSwitchingSession sera remis à false par la méthode appelante (createNewSession/switchSession) après la nouvelle connexion
            }
        };

        this._ws.onerror = (error) => {
            console.error("WebSocket error:", error);
            this.addMessage("WebSocket error. Check console.", "error-message");
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
            this.addMessage("Initializing session...", "system-message");
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
            this.setCurrentSessionId(sessionId);
            // Ne pas charger l\'historique ici si c\'est une tentative de reconnexion après une déconnexion
            // L\'historique est déjà chargé ou sera géré différemment
            if (!isReconnectAttempt) {
                this.addMessage("Using existing session: " + sessionId, "system-message");
                await this.loadChatHistory(USER_ID, sessionId);
            }
            this.connectToChatWebSocket(USER_ID, sessionId);
        } else {
            console.log("No session ID available, creating a new one via WebSocket...");
            try {
                const createSessionWsUrl = `${PUBLIC_FAST_API_WS_URL}/ws/create_session/${USER_ID}`;
                const sessionWs = new WebSocket(createSessionWsUrl);

                sessionWs.onopen = () => {
                    console.log("Connected to create_session endpoint.");
                };

                sessionWs.onmessage = async (event) => {
                    const data = JSON.parse(event.data);
                    if (data.type === "session_created" && data.session_id) {
                        sessionId = data.session_id;
                        if (sessionId) {
                            setCookie("chat_session_id", sessionId);
                        }
                        this.setCurrentSessionId(sessionId);
                        console.log("New session ID received and stored:", sessionId);
                        this.addMessage("Session created: " + sessionId, "system-message");
                        sessionWs.close();
                        if (sessionId) {
                            // Lancer le chargement de l\'historique après avoir obtenu un nouveau session_id
                            this.clearMessages(); // Vider les messages précédents
                            this.addMessage("New session created: " + sessionId, "system-message");
                            await this.loadChatHistory(USER_ID, sessionId);
                            this.connectToChatWebSocket(USER_ID, sessionId);
                            await this.loadUserSessions(USER_ID); // Recharger la liste des sessions
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
                this._userSessions = data.sessions.sort((a, b) => b.last_update_time - a.last_update_time);
                console.log("User sessions loaded:", this._userSessions);
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
        if (this._ws && this._ws.readyState === WebSocket.OPEN) {
            this._ws.close();
        }
        this.setConnected(false); // Mettre à jour l'état de connexion immédiatement

        removeCookie("chat_session_id");
        this.setCurrentSessionId(null);

        // La création de session se fait via initializeSessionAndConnect si aucun cookie n'est trouvé
        // Elle mettra à jour l'UI et la liste des sessions une fois terminée
        await this.initializeSessionAndConnect(null, false); // false car ce n'est pas une reconnexion auto
        // isSwitchingSession sera remis à false par onopen ou onerror de la nouvelle connexion WebSocket
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

// Fonction utilitaire pour supprimer un cookie
/**
 * @param {string} name
 */
function removeCookie(name) {
    if (typeof document === 'undefined') return; // Garde-fou pour SSR
    document.cookie = name + '=; Path=/; Expires=Thu, 01 Jan 1970 00:00:01 GMT;';
}
