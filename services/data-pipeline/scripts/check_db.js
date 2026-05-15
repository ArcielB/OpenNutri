import pkg from 'pg';
import process from 'node:process';
const { Client } = pkg;

const connectionString = process.env.DATABASE_URL;

if (!connectionString) {
    throw new Error('Missing DATABASE_URL.');
}

async function main() {
    const client = new Client({ connectionString });
    try {
        await client.connect();
        const res = await client.query('SELECT id, title, filename FROM papers');
        console.log('Papers in DB:');
        console.table(res.rows);
    } catch (err) {
        console.error('Failed:', err);
    } finally {
        await client.end();
    }
}

main();
