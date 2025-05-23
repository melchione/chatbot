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
