<script>
    import { onMount } from "svelte";
    import { chatState } from "$lib/chatLogic.svelte.js";

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
        {#each chatState.messages as message (message.id)}
            <div
                class="mb-2.5 p-2.5 rounded-2xl max-w-[75%] break-words leading-normal flex flex-col {message.type ===
                    'user-message' || message.type === 'user-image'
                    ? 'bg-blue-600 text-white ml-auto rounded-br-md'
                    : ''} {message.type === 'agent-message'
                    ? 'bg-gray-200 text-gray-800 mr-auto rounded-bl-md'
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
                {@html message.text}
            </div>
        {/each}
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
