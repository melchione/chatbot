<script>
    import { onMount } from "svelte";
    import { chatState } from "$lib/chatLogic.svelte.js";
    import { enhance } from "$app/forms";

    /** @type {import('./$types').PageData} */
    let { data } = $props(); // Données venant de la fonction load (+page.server.js)

    let messageInput = $state("");
    /** @type {HTMLDivElement | null} */
    let messagesArea = null;
    let autoScroll = $state(true);

    onMount(async () => {
        // Passer l'ID de session de `load` à la logique d'initialisation
        await chatState.initializeSessionAndConnect();
        scrollToBottom(); // Scroll initial après chargement potentiel de l'historique
    });

    function scrollToBottom() {
        if (messagesArea && autoScroll) {
            messagesArea.scrollTop = messagesArea.scrollHeight;
        }
    }

    $effect(() => {
        scrollToBottom();
    });

    function handleScroll() {
        if (messagesArea) {
            // Si l'utilisateur a scrollé vers le haut, désactiver l'auto-scroll
            const isScrolledToBottom =
                messagesArea.scrollHeight - messagesArea.clientHeight <=
                messagesArea.scrollTop + 1;
            autoScroll = isScrolledToBottom;
        }
    }

    async function handleSubmit(event) {
        event.preventDefault();
        if (!messageInput.trim()) return;
        chatState.sendTextMessage(messageInput.trim());
        messageInput = ""; // Clear input after sending
        autoScroll = true; // Réactiver l'auto-scroll lors de l'envoi d'un message
        // La fonction enhance s'occupera de la soumission du formulaire au serveur
        // et de la gestion de la réponse si nécessaire.
        // Ici, sendMessage s'occupe de l'aspect WebSocket.
    }
</script>

<svelte:head>
    <title>SvelteKit Vertex AI Chat</title>
</svelte:head>

<div class="chat-container">
    <h1>SvelteKit Vertex AI Chat</h1>
    <div bind:this={messagesArea} class="messages-area" onscroll={handleScroll}>
        {#each chatState.messages as message (message.id)}
            <div class="message {message.type}" data-event-id={message.id}>
                {@html message.text}
                <!-- Utiliser @html car chatLogic peut contenir des <br> -->
            </div>
        {/each}
    </div>
    <form
        method="POST"
        use:enhance={() => {
            // Callback pour l'amélioration progressive
            // Permet de gérer le retour de l'action du formulaire si nécessaire
            return async ({ result, update }) => {
                if (result.type === "success") {
                    // Le message est déjà ajouté localement par sendMessage via WebSocket.
                    // On pourrait ici gérer des retours spécifiques du serveur si l'action faisait plus.
                } else if (result.type === "failure") {
                    // Gérer les erreurs de validation du formulaire retournées par le serveur
                    console.error("Form submission error:", result.data);
                    // On pourrait afficher un message d'erreur à l'utilisateur
                }
                await update(); // Met à jour l'état de la page si nécessaire
            };
        }}
        onsubmit={handleSubmit}
        class="message-form"
    >
        <input
            type="text"
            name="message"
            bind:value={messageInput}
            autocomplete="off"
            placeholder="Type your message..."
            disabled={!chatState.isConnected}
        />
        <button
            type="submit"
            disabled={!chatState.isConnected || !messageInput.trim()}
            >Send</button
        >
    </form>
</div>

<style>
    .chat-container {
        font-family: sans-serif;
        margin: 20px;
        display: flex;
        flex-direction: column;
        height: calc(100vh - 40px); /* Full height minus margins */
        max-width: 600px;
        margin-left: auto;
        margin-right: auto;
        background-color: #fff;
        border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    }

    h1 {
        text-align: center;
        color: #333;
        padding: 15px 0;
        border-bottom: 1px solid #eee;
        margin-top: 0;
    }

    .messages-area {
        flex-grow: 1;
        overflow-y: auto;
        border: 1px solid #eee;
        padding: 15px;
        margin: 0 15px 15px 15px;
        background-color: #f9f9f9;
        border-radius: 5px;
    }

    .message {
        margin-bottom: 10px;
        padding: 10px 15px;
        border-radius: 15px;
        max-width: 75%;
        word-wrap: break-word;
        line-height: 1.4;
    }

    .user-message {
        background-color: #007bff;
        color: white;
        text-align: left; /* Convention: message utilisateur à gauche mais stylé comme "envoyé" */
        margin-left: auto; /* Aligns to the right */
        border-bottom-right-radius: 5px;
    }

    .agent-message {
        background-color: #e9ecef;
        color: #333;
        text-align: left;
        margin-right: auto; /* Aligns to the left */
        border-bottom-left-radius: 5px;
    }

    .system-message {
        font-style: italic;
        color: #6c757d;
        text-align: center;
        font-size: 0.9em;
        padding: 5px 0;
    }

    .error-message {
        background-color: #f8d7da;
        color: #721c24;
        border: 1px solid #f5c6cb;
        font-weight: bold;
        border-radius: 5px;
    }

    .message-form {
        display: flex;
        padding: 15px;
        border-top: 1px solid #eee;
    }

    .message-form input {
        flex-grow: 1;
        padding: 12px;
        margin-right: 10px;
        border: 1px solid #ccc;
        border-radius: 20px;
        font-size: 1em;
    }
    .message-form input:focus {
        outline: none;
        border-color: #007bff;
        box-shadow: 0 0 0 0.2rem rgba(0, 123, 255, 0.25);
    }

    .message-form button {
        padding: 12px 20px;
        border: none;
        background-color: #007bff;
        color: white;
        border-radius: 20px;
        cursor: pointer;
        font-size: 1em;
        transition: background-color 0.2s ease;
    }

    .message-form button:hover {
        background-color: #0056b3;
    }

    .message-form button:disabled {
        background-color: #c0c0c0;
        cursor: not-allowed;
    }
</style>
