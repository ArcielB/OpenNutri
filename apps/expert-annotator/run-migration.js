import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import pkg from 'pg';

const { Client } = pkg;

const migrationPath = path.join(process.cwd(), 'migration.sql');
const connectionString = process.env.DATABASE_URL;

if (!connectionString) {
  console.error('Missing DATABASE_URL. Refusing to use hardcoded database credentials.');
  process.exit(1);
}

if (!fs.existsSync(migrationPath)) {
  console.error(`Missing migration file at ${migrationPath}`);
  process.exit(1);
}

const sql = fs.readFileSync(migrationPath, 'utf8');

async function main() {
  const client = new Client({ connectionString });
  try {
    await client.connect();
    console.log('Connected to database. Running migration.sql...');
    await client.query(sql);
    console.log('Migration completed successfully.');
  } catch (error) {
    console.error('Migration failed:', error);
    process.exitCode = 1;
  } finally {
    await client.end();
  }
}

main();
