// import { writable } from 'svelte/store'; // Supprimé
import { PUBLIC_FAST_API_URL, PUBLIC_FAST_API_WS_URL } from '$env/static/public';

const USER_ID = "test_user"; // User ID fixe pour le moment

/**
 * @typedef {{id: string | number, text: string, type: string, completed?: boolean}} Message
 */

class ChatState {
    /** @type {Array<Message>} */
    #messages = $state([]);
    #isConnected = $state(false);
    /** @type {string | null} */
    #currentSessionId = $state(null);
    /** @type {WebSocket | null} */
    #ws = null;
    #isThinking = $state(false);

    constructor() {
        // Initialisation si nécessaire, ou laisser vide si $state gère l'initialisation
    }

    // Getters pour l'accès en lecture seule de l'extérieur si nécessaire
    // (Svelte 5 runes rendent souvent cela implicite via la réactivité de $state)
    get messages() {
        return this.#messages;
    }

    get isThinking() {
        return this.#isThinking;
    }

    get isConnected() {
        return this.#isConnected;
    }

    get currentSessionId() {
        return this.#currentSessionId;
    }

    // Méthodes pour modifier l'état
    /**
     * @param {string} text
     * @param {string} type
     * @param {string | number | null} [eventId=null]
     */
    addMessage(text, type, eventId = null) {
        if (eventId && this.#messages.some(msg => msg.id === eventId)) {
            return;
        }
        const newMessage = { text, type, id: eventId || Date.now() + Math.random().toString(36) };
        this.#messages = [...this.#messages, newMessage];
    }

    /**
     * @param {string} text
     */
    updateLastMessagePart(text) {
        if (this.#messages.length > 0) {
            let lastMessage = this.#messages[this.#messages.length - 1];
            if (lastMessage && lastMessage.type === "agent-message" && !lastMessage.completed) {
                const updatedText = lastMessage.text + text.replace(/\n/g, "<br>");
                this.#messages = [
                    ...this.#messages.slice(0, -1),
                    { ...lastMessage, text: updatedText }
                ];
            } else {
                this.addMessage(text.replace(/\n/g, "<br>"), "agent-message");
            }
        }
    }

    completeLastMessage() {
        if (this.#messages.length > 0) {
            let lastMessage = this.#messages[this.#messages.length - 1];
            if (lastMessage && lastMessage.type === "agent-message" && !lastMessage.completed) {
                this.#messages = [
                    ...this.#messages.slice(0, -1),
                    { ...lastMessage, completed: true }
                ];
            }
        }
    }

    /**
     * @param {boolean} status
     */
    setConnected(status) {
        this.#isConnected = status;
    }

    /**
     * @param {string | null} sessionId
     */
    setCurrentSessionId(sessionId) {
        this.#currentSessionId = sessionId;
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
                const filteredCurrentMessages = this.#messages.filter(msg => !(msg.text === "Loading chat history..." && msg.type === "system-message"));
                const historyMessages = data.events.map(/** @param {any} event */ event => {
                    if (event.content && event.content.parts && event.content.parts.length > 0) {
                        const part = event.content.parts[0];
                        if (part.text) {
                            return {
                                text: part.text.replace(/\n/g, "<br>"),
                                type: event.author === 'user' ? "user-message" : "agent-message",
                                id: event.id
                            };
                        }
                    }
                    return null;
                }).filter(
                    /**
                    * @param {(Message | null)} m
                    * @returns {m is Message}
                    */
                    m => m !== null
                );
                this.#messages = [...filteredCurrentMessages, ...historyMessages];
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
        this.#ws = new WebSocket(chatWsUrl);

        this.#ws.onopen = () => {
            console.log("Connected to WebSocket server with User ID:", userId, "and Session ID:", sessionId);
            this.setConnected(true);
            this.addMessage("Connected to agent.", "system-message");
        };

        this.#ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log("Received:", data);
            if (data.type === "message_part" && data.text) {
                this.updateLastMessagePart(data.text);
            } else if (data.type === "message_end") {
                this.completeLastMessage();
            } else if (data.type === "error" && data.message) {
                this.addMessage("Error: " + data.message, "error-message");
            } else if (data.text) { // Cas générique pour les messages texte non structurés différemment
                this.addMessage(data.text, "agent-message");
            }
        };

        this.#ws.onclose = () => {
            console.log("Disconnected from WebSocket server.");
            this.setConnected(false);
            this.addMessage("Disconnected. Attempting to reconnect in 5 seconds...", "system-message");
            setTimeout(() => this.initializeSessionAndConnect(null, true), 5000);
        };

        this.#ws.onerror = (error) => {
            console.error("WebSocket error:", error);
            this.addMessage("WebSocket error. Check console.", "error-message");
            if (this.#ws) this.#ws.close();
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
        }

        let sessionId = initialSessionIdFromLoad;

        if (!sessionId) {
            sessionId = getCookie("chat_session_id");
        }

        if (!sessionId) {
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
                        if (sessionId) this.connectToChatWebSocket(USER_ID, sessionId);
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
        } else {
            console.log("Using existing session ID from cookies or load: ", sessionId);
            this.setCurrentSessionId(sessionId);
            this.addMessage("Using existing session: " + sessionId, "system-message");
            await this.loadChatHistory(USER_ID, sessionId);
            this.connectToChatWebSocket(USER_ID, sessionId);
        }
    }

    /**
     * @param {string} messageText
     */
    sendMessage(messageText) {
        if (messageText && this.#ws && this.#ws.readyState === WebSocket.OPEN) {
            const payload = {
                type: "text",
                data: messageText
            };
            this.#isThinking = true;

            this.#ws.send(JSON.stringify(payload));
            this.#isThinking = false;

            this.addMessage(messageText, "user-message");
        } else {
            this.addMessage("Cannot send message. WebSocket not connected or message is empty.", "error-message");
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
