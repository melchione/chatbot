<script>
    import ChatInterface from "$lib/components/ChatInterface.svelte";
    import SessionSidebar from "$lib/components/SessionSidebar.svelte";
    import { onMount } from "svelte";
    import { initializeSessionAndConnect } from "$lib/chatLogic.svelte.js";

    onMount(() => {
        initializeSessionAndConnect();
    });
</script>

<div class="flex w-full h-full">
    <SessionSidebar />
    <ChatInterface />
</div>
