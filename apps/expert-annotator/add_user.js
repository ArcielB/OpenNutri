import { createClient } from '@supabase/supabase-js';

// Load directly to avoid dotenv dependency issues
const supabaseUrl = 'https://mlirsjgolmryywlfahuf.supabase.co';
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1saXJzamdvbG1yeXl3bGZhaHVmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjkyOTM5MDksImV4cCI6MjA4NDg2OTkwOX0.A1skN5u-E6AT10n3iDfh36yU7knCV2NYHZXmJhfwLmM';

const supabase = createClient(supabaseUrl, supabaseAnonKey);

async function main() {
    console.log('[DEBUG] Starting user creation for: mcraft160105@gmail.com');
    try {
        const { data, error } = await supabase.auth.signUp({
            email: 'mcraft160105@gmail.com',
            password: 'Password123!',
        });

        if (error) {
            console.error('[ERROR] Error signing up:', error.message);
        } else {
            console.log('[SUCCESS] Signup successful!');
            console.log('User ID:', data.user?.id);
        }
    } catch (e) {
        console.error('[FATAL]', e);
    }
    console.log('[DEBUG] Exiting script');
    process.exit(0);
}

main();
