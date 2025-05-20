import { fail } from '@sveltejs/kit';

// TODO: Gérer la récupération et la création de session ID via les cookies ici dans une fonction load.

export async function load({ cookies }) {
    const sessionId = cookies.get('chat_session_id');
    // Pour l'instant, on ne fait que passer l'ID de session existant.
    // La logique de création de session reste initiée côté client via WebSocket pour le moment.
    return {
        sessionId: sessionId || null // Assure que l'on passe null si undefined
    };
}

export const actions = {
    default: async ({ request, cookies }) => {
        const formData = await request.formData();
        const message = formData.get('message');

        if (!message || message.toString().trim() === '') {
            return fail(400, { message, missing: true });
        }

        // À ce stade, nous ne faisons que simuler la logique d'envoi.
        // Dans une implémentation complète, vous enverriez ce message
        // au backend WebSocket ou à une API.
        console.log(`Message reçu sur le serveur (simulation): ${message}`);

        // Pour l'instant, nous n'interagissons pas directement avec le chatLogic.js côté client depuis ici.
        // Le client (dans +page.svelte) utilisera chatLogic.js pour envoyer via WebSocket.
        // Cette action de formulaire est surtout pour la validation et pourrait être utilisée 
        // pour des opérations synchrones ou pour déclencher des événements côté serveur.

        // Simuler une réponse ou une redirection si nécessaire
        // Par exemple, pour vider le formulaire, la logique se trouvera dans le +page.svelte avec enhance
        return { success: true, sentMessage: message.toString() };
    }
};

// Fonction load pour passer des données initiales à la page (par exemple, l'ID de session depuis les cookies)
// export async function load({ cookies }) {
//     let sessionId = cookies.get('chat_session_id');
//     if (!sessionId) {
// Logique pour en créer un nouveau si nécessaire, potentiellement via un endpoint interne
// Pour l'instant, on laisse le client gérer la création via WebSocket comme dans l'original
//     }
//     return {
//         sessionId: sessionId
//     };
// } 