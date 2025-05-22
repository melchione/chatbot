<script>
    import {
        createNewSession,
        switchSession,
        getUserSessions,
        getCurrentSessionId,
        deleteSelectedSession,
    } from "$lib/chatLogic.svelte.js";

    // USER_ID est défini dans chatLogic, mais nous en avons besoin ici pour les actions
    // Idéalement, cela viendrait d'un store d'authentification ou d'un contexte plus global
    const USER_ID = "test_user";

    // Accès aux états et getters via les runes de Svelte 5 (si chatState utilise $state)
    // ou via des stores Svelte classiques si chatState est un writable store.
    // Pour cet exemple, nous allons supposer que getUserSessions() et getCurrentSessionId()
    // retournent des valeurs réactives (par exemple, si elles sont dérivées de $state).

    // Pour Svelte 5 avec des runes, si getUserSessions et getCurrentSessionId sont des getters
    // sur un objet chatState qui utilise $state, la réactivité est gérée.
    // Si ce sont des fonctions qui retournent des snapshots, il faudrait les appeler dans
    // des contextes réactifs ou utiliser $derived.

    // On récupère les sessions et l'ID de la session courante
    // Svelte 5 $derived pour la réactivité:
    let sessions = $derived(getUserSessions());
    let currentSessionId = $derived(getCurrentSessionId());

    async function handleCreateNewSession() {
        await createNewSession(USER_ID);
    }

    /** @param {string} sessionId */
    async function handleSwitchSession(sessionId) {
        if (sessionId !== currentSessionId) {
            await switchSession(USER_ID, sessionId);
        }
    }

    /**
     * @param {Event} e
     * @param {string} sessionId
     */
    async function confirmAndDelete(e, sessionId) {
        e.stopPropagation(); // Empêche le clic de déclencher handleSwitchSession sur le <li> parent
        if (
            window.confirm(
                `Êtes-vous sûr de vouloir supprimer la session ${sessionId.substring(0, 8)}...?`,
            )
        ) {
            await deleteSelectedSession(USER_ID, sessionId);
        }
    }

    /** @param {number | undefined} timestamp */
    function formatDate(timestamp) {
        if (!timestamp) return "N/A"; // Si last_update_time n'est pas disponible
        // Convertir le timestamp Unix (secondes) en millisecondes
        const date = new Date(timestamp * 1000);
        return date.toLocaleString(); // Ou un format plus personnalisé
    }
</script>

<div class="w-[280px] p-4 flex flex-col h-full">
    <button
        class="bg-green-500 text-white py-3 px-4 rounded-md cursor-pointer text-base mb-5 transition-colors duration-200 hover:bg-green-600"
        on:click={handleCreateNewSession}
    >
        Nouvelle Session (+)
    </button>
    <ul class="list-none p-0 m-0 overflow-y-auto flex-grow">
        {#if sessions && sessions.length > 0}
            {#each sessions as session (session.session_id)}
                <li
                    class="p-3 my-1 cursor-pointer transition-colors duration-200 hover:bg-gray-200 last:border-b-0 {session.session_id ===
                    currentSessionId
                        ? 'bg-blue-100 font-bold bg-white/50 backdrop-blur-xl'
                        : ''}"
                    on:click={() => handleSwitchSession(session.session_id)}
                    role="button"
                    tabindex="0"
                    on:keydown={(e) =>
                        e.key === "Enter" &&
                        handleSwitchSession(session.session_id)}
                >
                    <div class="flex justify-between items-center">
                        <div class="text-sm text-gray-800 mb-1">
                            {formatDate(session.last_update_time)}
                        </div>
                        <button
                            on:click={(e) =>
                                confirmAndDelete(e, session.session_id)}
                            on:keydown={(e) => {
                                e.stopPropagation();
                                if (e.key === "Enter")
                                    confirmAndDelete(e, session.session_id);
                            }}
                            class="text-red-500 hover:text-red-700 p-1 rounded-full hover:bg-red-100 transition-colors duration-150 text-sm"
                            aria-label="Supprimer la session"
                        >
                            &#x2715; <!-- C'est un X (multiplication sign) -->
                        </button>
                    </div>
                </li>
            {/each}
        {:else}
            <li class="text-gray-500 p-3 text-center">
                Aucune session trouvée.
            </li>
        {/if}
    </ul>
</div>
