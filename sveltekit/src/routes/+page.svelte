<script>
    import ChatInterface from "$lib/components/ChatInterface.svelte";
    import SessionSidebar from "$lib/components/SessionSidebar.svelte";
    import { onMount } from "svelte";
    import { initializeSessionAndConnect } from "$lib/chatLogic.svelte.js";

    onMount(() => {
        initializeSessionAndConnect();
    });
</script>

<div
    class="flex w-full h-full bg-linear-115 from-[#fff1be] from-28% via-[#ee87cb] via-70% to-[#b060ff] sm:bg-linear-145"
>
    <SessionSidebar />
    <ChatInterface />
</div>
