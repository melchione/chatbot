import { streamAgentQuery } from '$lib/server/vertex_ai_client.js';

/** @type {import('./$types').RequestHandler} */
export async function POST({ request }) {
    try {
        const body = await request.json();
        const { userId, sessionId, message } = body;

        if (!userId || typeof userId !== 'string') {
            return new Response(JSON.stringify({ error: 'userId (string) is required' }), {
                status: 400,
                headers: { 'Content-Type': 'application/json' }
            });
        }
        if (!sessionId || typeof sessionId !== 'string') {
            return new Response(JSON.stringify({ error: 'sessionId (string) is required' }), {
                status: 400,
                headers: { 'Content-Type': 'application/json' }
            });
        }
        if (!message || typeof message !== 'object') {
            return new Response(JSON.stringify({ error: 'message (object) is required' }), {
                status: 400,
                headers: { 'Content-Type': 'application/json' }
            });
        }

        // L'implémentation actuelle de streamAgentQuery retourne un stream simulé
        const agentResponseStream = await streamAgentQuery(userId, sessionId, message);
        console.log(`[API /api/chat/message] Streaming message for session ${sessionId}`);

        return new Response(agentResponseStream, {
            headers: {
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
            }
        });

    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Failed to send message due to an unknown error';
        console.error('[API Error /api/chat/message] streamAgentQuery:', errorMessage, error);
        return new Response(JSON.stringify({ error: errorMessage }), {
            status: 500,
            headers: { 'Content-Type': 'application/json' }
        });
    }
} 