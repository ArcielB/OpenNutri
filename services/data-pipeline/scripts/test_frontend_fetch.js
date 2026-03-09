import { createClient } from '@supabase/supabase-js'
import dotenv from 'dotenv'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
dotenv.config({ path: path.join(__dirname, '../../apps/expert-annotator/.env') })

const supabaseUrl = process.env.VITE_SUPABASE_URL
const supabaseAnonKey = process.env.VITE_SUPABASE_ANON_KEY

const supabase = createClient(supabaseUrl, supabaseAnonKey)

async function testFetch() {
    // 1. Without logging in (pure anon)
    console.log("Fetching papers without auth (anon):")
    let res1 = await supabase.from('papers').select('*')
    console.log(res1.error ? "Error: " + res1.error.message : `Found ${res1.data?.length || 0} papers as anon`)

    // 2. Sign in with the user we used before (I see mcraft160105@gmail.com in the logs)
    // Wait, we don't know the password. Let's just create an anon fetch and see if it fails.
}

testFetch()
