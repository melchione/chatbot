import { json } from '@sveltejs/kit';
import { createChatSession } from '$lib/server/vertex_ai_client.js';

/** @type {import('./$types').RequestHandler} */
export async function POST({ request }) {
    try {
        const body = await request.json();
        const userId = body.userId;

        if (!userId || typeof userId !== 'string') {
            return json({ error: 'userId (string) is required in the request body' }, { status: 400 });
        }

        // L'implémentation actuelle de createChatSession est un placeholder
        const sessionId = await createChatSession(userId);
        console.log(`[API /api/chat/session] Session created: ${sessionId} for user ${userId}`);

        return json({ sessionId });
    } catch (error) {
        // Gestion des erreurs plus générique
        const errorMessage = error instanceof Error ? error.message : 'Failed to create session due to an unknown error';
        console.error('[API Error /api/chat/session] createChatSession:', errorMessage, error);
        return json({ error: errorMessage }, { status: 500 });
    }
} 