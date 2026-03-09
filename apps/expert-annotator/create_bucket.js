import pkg from 'pg';
const { Client } = pkg;

const connectionString = 'postgresql://postgres:Al29minuto$@db.mlirsjgolmryywlfahuf.supabase.co:6543/postgres';

const sql = `
-- Insert the 'papers' bucket if it doesn't exist
INSERT INTO storage.buckets (id, name, public) 
VALUES ('papers', 'papers', true)
ON CONFLICT (id) DO NOTHING;

-- Allows anyone to read from the 'papers' bucket
CREATE POLICY "Public Access" 
ON storage.objects FOR SELECT 
USING ( bucket_id = 'papers' );

-- Allow authenticated users to insert files
CREATE POLICY "Authenticated users can upload papers"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK ( bucket_id = 'papers' );

-- Also allow anon to upload temporarily for our script, if needed, or we just rely on that we run the script via service role? 
-- The script uses ANON_KEY. Let's allow anon insert to papers bucket for now.
CREATE POLICY "Anon users can upload papers"
ON storage.objects FOR INSERT
TO anon
WITH CHECK ( bucket_id = 'papers' );

-- Same for UPDATE
CREATE POLICY "Anon users can update papers"
ON storage.objects FOR UPDATE
TO anon
USING ( bucket_id = 'papers' );
`;

async function main() {
    const client = new Client({ connectionString });
    try {
        await client.connect();
        console.log('Connected to DB. Creating storage bucket...');
        await client.query(sql);
        console.log('Storage bucket created successfully.');
    } catch (err) {
        console.error('Failed:', err);
    } finally {
        await client.end();
    }
}

main();
