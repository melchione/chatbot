<script>
    import { onMount } from "svelte";
    import { chatState, createNewSession } from "$lib/chatLogic.svelte.js";
    import { marked } from "marked";

    const USER_ID = "test_user";

    // Configuration de marked pour la sécurité et les fonctionnalités
    marked.setOptions({
        breaks: true, // Convertit les sauts de ligne en <br>
        gfm: true, // Support GitHub Flavored Markdown
    });

    // Fonction pour parser le markdown
    function parseMarkdown(text) {
        try {
            const result = marked.parse(text);
            // marked.parse peut retourner une string ou une Promise<string>
            if (typeof result === "string") {
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

    $effect(() => {
        scrollToBottom();
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
</script>

<svelte:head>
    <title>Agency Flow</title>
</svelte:head>

<div class="w-full">
    <div
        class="font-sans relative m-5 mb-0 flex flex-col h-[calc(100vh-118px)] max-w-2xl mx-auto"
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
            class="flex-grow overflow-y-auto p-4 mx-4 mb-4"
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
                            ? 'bg-blue-600 text-white max-w-[75%]  ml-auto rounded-br-md'
                            : ''} {message.type === 'agent-message'
                            ? 'bg-white text-gray-800 max-w-[75%]  mr-auto rounded-bl-md'
                            : ''} {message.type === 'system-message'
                            ? 'italic text-gray-500 text-center text-sm py-1'
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
                            {@html parseMarkdown(message.text)}
                        {:else}
                            {@html message.text}
                        {/if}
                    </div>
                {/each}
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

<style>
    /* Styles pour le contenu Markdown dans les messages d'agent */
    :global(.chat_message h1),
    :global(.chat_message h2),
    :global(.chat_message h3),
    :global(.chat_message h4),
    :global(.chat_message h5),
    :global(.chat_message h6) {
        font-weight: bold;
        margin: 0.5em 0 0.3em 0;
        line-height: 1.2;
        color: inherit;
    }

    :global(.chat_message h1) {
        font-size: 1.5em;
    }
    :global(.chat_message h2) {
        font-size: 1.3em;
    }
    :global(.chat_message h3) {
        font-size: 1.1em;
    }

    :global(.chat_message p) {
        margin: 0.5em 0;
    }

    :global(.chat_message ul),
    :global(.chat_message ol) {
        margin: 0.5em 0;
        padding-left: 1.5em;
    }

    :global(.chat_message li) {
        margin: 0.2em 0;
        list-style-type: disc;
    }

    :global(.chat_message code) {
        background-color: rgba(0, 0, 0, 0.1);
        padding: 0.2em 0.4em;
        border-radius: 0.25em;
        font-family: "Courier New", Courier, monospace;
        font-size: 0.9em;
    }

    :global(.chat_message pre) {
        background-color: rgba(0, 0, 0, 0.1);
        padding: 1em;
        border-radius: 0.5em;
        overflow-x: auto;
        margin: 0.5em 0;
    }

    :global(.chat_message pre code) {
        background-color: transparent;
        padding: 0;
    }

    :global(.chat_message blockquote) {
        border-left: 3px solid #666;
        margin: 0.5em 0;
        padding-left: 1em;
        font-style: italic;
        color: #555;
    }

    :global(.chat_message table) {
        border-collapse: collapse;
        margin: 0.5em 0;
        width: 100%;
    }

    :global(.chat_message th),
    :global(.chat_message td) {
        border: 1px solid #999;
        padding: 0.5em;
        text-align: left;
    }

    :global(.chat_message th) {
        background-color: rgba(0, 0, 0, 0.1);
        font-weight: bold;
    }

    :global(.chat_message strong) {
        font-weight: bold;
    }

    :global(.chat_message em) {
        font-style: italic;
    }

    :global(.chat_message a) {
        color: #0066cc;
        text-decoration: underline;
    }

    :global(.chat_message a:hover) {
        text-decoration: none;
    }
</style>
