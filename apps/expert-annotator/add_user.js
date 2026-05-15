import { createClient } from '@supabase/supabase-js';
import process from 'node:process';

const supabaseUrl = process.env.VITE_SUPABASE_URL || process.env.SUPABASE_URL;
const supabaseAnonKey = process.env.VITE_SUPABASE_ANON_KEY || process.env.SUPABASE_ANON_KEY;
const signupEmail = process.env.SIGNUP_EMAIL;
const signupPassword = process.env.SIGNUP_PASSWORD;

if (!supabaseUrl || !supabaseAnonKey || !signupEmail || !signupPassword) {
    throw new Error('Missing VITE_SUPABASE_URL/SUPABASE_URL, VITE_SUPABASE_ANON_KEY/SUPABASE_ANON_KEY, SIGNUP_EMAIL, or SIGNUP_PASSWORD.');
}

const supabase = createClient(supabaseUrl, supabaseAnonKey);

async function main() {
    console.log(`[DEBUG] Starting user creation for: ${signupEmail}`);
    try {
        const { data, error } = await supabase.auth.signUp({
            email: signupEmail,
            password: signupPassword,
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
