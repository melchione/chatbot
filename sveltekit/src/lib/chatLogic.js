import { writable } from 'svelte/store';
import { PUBLIC_FAST_API_URL, PUBLIC_FAST_API_WS_URL } from '$env/static/public';

/** @type {import('svelte/store').Writable<Array<{id: string | number, text: string, type: string, completed?: boolean}>>} */
export const messages = writable([]);
/** @type {import('svelte/store').Writable<boolean>} */
export const isConnected = writable(false);
/** @type {import('svelte/store').Writable<string | null>} */
export const currentSessionId = writable(null);

const USER_ID = "test_user"; // User ID fixe pour le moment
/** @type {WebSocket | null} */
let ws = null;

/**
 * @param {string} text
 * @param {string} type
 * @param {string | number | null} [eventId=null]
 */
function addMessageToStore(text, type, eventId = null) {
    messages.update(currentMessages => {
        if (eventId && currentMessages.some(msg => msg.id === eventId)) {
            return currentMessages;
        }
        const newMessage = { text, type, id: eventId || Date.now() + Math.random().toString(36) };
        return [...currentMessages, newMessage];
    });
    // Auto-scroll géré dans le composant Svelte via une action ou $: après la mise à jour de messages
}

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

/**
 * @param {string} userId
 * @param {string} sessionId
 */
async function loadChatHistory(userId, sessionId) {
    addMessageToStore("Loading chat history...", "system-message");
    try {
        // Construire l'URL de l'historique en utilisant la variable d'environnement pour la base de l'URL HTTP
        // On suppose que l'API HTTP est servie sur la même base que les WS, mais avec http(s)://
        const httpBaseUrl = PUBLIC_FAST_API_URL;
        const historyUrl = `${httpBaseUrl}/session_history/${userId}/${sessionId}`;
        const response = await fetch(historyUrl);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: "Failed to fetch history, server returned: " + response.status }));
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        if (data.events && data.events.length > 0) {
            messages.update(currentMessages => {
                const filteredMessages = currentMessages.filter(msg => !(msg.text === "Loading chat history..." && msg.type === "system-message"));
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
                }).filter(Boolean); // Filter out nulls explicitly
                return [...filteredMessages, ...historyMessages.filter(
                    /** 
                     * @param {({id: string | number, text: string, type: string} | null)} m 
                     * @returns {m is {id: string | number, text: string, type: string}} 
                     */
                    m => m !== null
                )];
            });
            addMessageToStore("Chat history loaded.", "system-message");
        } else {
            addMessageToStore("No previous chat history found or session is new.", "system-message");
        }
    } catch (error) {
        console.error("Error loading chat history:", error);
        if (error instanceof Error) {
            addMessageToStore("Error loading chat history: " + error.message, "error-message");
        } else {
            addMessageToStore("An unknown error occurred while loading chat history.", "error-message");
        }
    }
}

/**
 * @param {string} userId
 * @param {string} sessionId
 */
function connectToChatWebSocket(userId, sessionId) {
    if (!sessionId) { // Guard clause for sessionId being null/undefined
        addMessageToStore("Error: No session ID available to connect to chat.", "error-message");
        isConnected.set(false);
        return;
    }
    // Utiliser la variable d'environnement pour l'URL de base du WebSocket
    const chatWsUrl = `${PUBLIC_FAST_API_WS_URL}/ws/${userId}/${sessionId}`;
    ws = new WebSocket(chatWsUrl);

    ws.onopen = () => {
        console.log("Connected to WebSocket server with User ID:", userId, "and Session ID:", sessionId);
        isConnected.set(true);
        addMessageToStore("Connected to agent.", "system-message");
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log("Received:", data);
        if (data.type === "message_part" && data.text) {
            messages.update(currentMessages => {
                let lastMessage = currentMessages[currentMessages.length - 1];
                if (lastMessage && lastMessage.type === "agent-message" && !lastMessage.completed) {
                    lastMessage.text += data.text.replace(/\n/g, "<br>");
                    return [...currentMessages.slice(0, -1), lastMessage];
                } else {
                    return [...currentMessages, { text: data.text.replace(/\n/g, "<br>"), type: "agent-message", completed: false, id: Date.now() + Math.random().toString(36) }];
                }
            });
        } else if (data.type === "message_end") {
            messages.update(currentMessages => {
                let lastMessage = currentMessages[currentMessages.length - 1];
                if (lastMessage && lastMessage.type === "agent-message") {
                    lastMessage.completed = true;
                    return [...currentMessages.slice(0, -1), lastMessage];
                }
                return currentMessages;
            });
        } else if (data.type === "error" && data.message) {
            addMessageToStore("Error: " + data.message, "error-message");
        } else if (data.text) {
            addMessageToStore(data.text, "agent-message");
        }
    };

    ws.onclose = () => {
        console.log("Disconnected from WebSocket server.");
        isConnected.set(false);
        addMessageToStore("Disconnected. Attempting to reconnect in 5 seconds...", "system-message");
        setTimeout(() => initializeSessionAndConnect(null, true), 5000);
    };

    ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        addMessageToStore("WebSocket error. Check console.", "error-message");
        if (ws) ws.close(); // Check if ws is not null before calling close
    };
}

/**
 * @param {string | null} [initialSessionIdFromLoad=null]
 * @param {boolean} [isReconnectAttempt=false]
 */
export async function initializeSessionAndConnect(initialSessionIdFromLoad = null, isReconnectAttempt = false) {
    isConnected.set(false);
    if (!isReconnectAttempt) {
        addMessageToStore("Initializing session...", "system-message");
    }

    let sessionId = initialSessionIdFromLoad;

    if (!sessionId) {
        sessionId = getCookie("chat_session_id");
    }

    if (!sessionId) {
        console.log("No session ID available, creating a new one via WebSocket...");
        try {
            // Utiliser la variable d'environnement pour l'URL de base du WebSocket
            const createSessionWsUrl = `${PUBLIC_FAST_API_WS_URL}/ws/create_session/${USER_ID}`;

            const sessionWs = new WebSocket(createSessionWsUrl);

            sessionWs.onopen = () => {
                console.log("Connected to create_session endpoint.");
            };

            sessionWs.onmessage = async (event) => {
                const data = JSON.parse(event.data);
                if (data.type === "session_created" && data.session_id) {
                    sessionId = data.session_id;
                    if (sessionId) { // Ensure sessionId is a string before setting cookie
                        setCookie("chat_session_id", sessionId);
                    }
                    currentSessionId.set(sessionId);
                    console.log("New session ID received and stored:", sessionId);
                    addMessageToStore("Session created: " + sessionId, "system-message");
                    sessionWs.close();
                    if (sessionId) connectToChatWebSocket(USER_ID, sessionId); // Guard with if(sessionId)
                } else {
                    console.error("Failed to create session:", data);
                    addMessageToStore("Error: Could not create session. " + (data.message || ""), "error-message");
                }
            };
            sessionWs.onerror = (error) => {
                console.error("WebSocket error during session creation:", error);
                addMessageToStore("Error: Could not connect to create session. Check console.", "error-message");
                isConnected.set(false);
            };

            sessionWs.onclose = () => {
                console.log("Session creation WebSocket closed.");
            };

        } catch (error) {
            console.error("Failed to connect to session creation endpoint:", error);
            if (error instanceof Error) {
                addMessageToStore("Fatal error: Could not initiate session creation. " + error.message, "error-message");
            } else {
                addMessageToStore("Fatal error: Could not initiate session creation. Check console.", "error-message");
            }
        }
    } else {
        console.log("Using existing session ID from cookies or load: ", sessionId);
        currentSessionId.set(sessionId); // sessionId is confirmed to be a string here or from getCookie
        addMessageToStore("Using existing session: " + sessionId, "system-message");
        await loadChatHistory(USER_ID, sessionId); // sessionId is a string here
        connectToChatWebSocket(USER_ID, sessionId); // sessionId is a string here
    }
}

/**
 * @param {string} messageText
 */
export function sendMessage(messageText) {
    if (messageText && ws && ws.readyState === WebSocket.OPEN) {
        const payload = {
            type: "text",
            data: messageText
        };
        ws.send(JSON.stringify(payload));
        addMessageToStore(messageText, "user-message");
    } else {
        addMessageToStore("Cannot send message. WebSocket not connected or message is empty.", "error-message");
    }
}

// Initialiser la session au chargement du module si nous sommes côté client
if (typeof window !== 'undefined') {
    // L'initialisation est maintenant appelée depuis onMount dans +page.svelte
} 