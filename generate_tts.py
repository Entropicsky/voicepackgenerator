#!/usr/bin/env python3
import os
import json
import csv
import requests
import random
from dotenv import load_dotenv
from datetime import datetime
from backend.models import init_db, SessionLocal, Take
from backend.seeder import upsert_game, upsert_skin, upsert_voice, create_batch

load_dotenv()

def main():
    # Load configuration
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    # Initialize database and open session
    init_db()
    session = SessionLocal()

    output_format = config.get('output_format', 'mp3_44100_128')
    variants = config.get('variants', 1)
    skinname = config.get('skinname', 'default')
    # Create a base batch ID (timestamp) for this run
    base_batch_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    # Upsert game and skin records
    game_obj = upsert_game(session, config.get('game'))
    skin_obj = upsert_skin(session, game_obj.id, skinname)

    # Get API key from environment
    api_key = os.getenv('ELEVENLABS_API_KEY')
    if not api_key:
        print('Error: Please set the ELEVENLABS_API_KEY environment variable.')
        return

    headers = {
        'xi-api-key': api_key,
        'Content-Type': 'application/json'
    }

    # Ensure base output directory for this skin exists
    base_output = os.path.join('output', skinname)
    os.makedirs(base_output, exist_ok=True)

    # Loop through each voice and generate variants
    for voice_id in config['voice_ids']:
        # Fetch voice metadata to get human-readable name
        meta_url = f'https://api.elevenlabs.io/v1/voices/{voice_id}'
        resp_meta = requests.get(meta_url, headers=headers)
        if resp_meta.status_code == 200:
            voice_meta = resp_meta.json()
            voice_name_human = voice_meta.get('name', voice_id)
        else:
            print(f'Warning: could not fetch name for {voice_id}, using ID instead')
            voice_name_human = voice_id
        # Sanitize and combine name and ID for voice folder
        folder_name = f"{voice_name_human}-{voice_id}"
        voice_root = os.path.join(base_output, folder_name)
        os.makedirs(voice_root, exist_ok=True)
        # Create a unique batch_tag and subfolder for this voice run
        batch_id = f"{base_batch_id}-{voice_id[:4]}"
        batch_dir = os.path.join(voice_root, batch_id)
        os.makedirs(batch_dir, exist_ok=True)

        # Seed DB: upsert voice and create batch record
        voice_obj = upsert_voice(session, voice_id, skin_obj.id, voice_name_human)
        batch_obj = create_batch(session, voice_obj.id, batch_id)

        # Initialize metadata list for this voice batch
        metadata = []

        csv_path = os.path.join('input', 'jingweidragonheart-audition.csv')
        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                name = row['Function']
                text = row['Line']
                for take in range(1, variants + 1):
                    # Random sampling of settings
                    stability = random.uniform(*config['stability_range'])
                    similarity_boost = random.uniform(*config['similarity_boost_range'])
                    style = random.uniform(*config['style_range'])
                    speed = random.uniform(*config['speed_range'])
                    settings = {
                        'stability': stability,
                        'similarity_boost': similarity_boost,
                        'style': style,
                        'use_speaker_boost': config.get('use_speaker_boost', False),
                        'speed': speed
                    }

                    print(f'Generating {name}, voice {voice_id}, take {take}...')
                    url = f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}'
                    params = {'output_format': output_format}
                    payload = {
                        'text': text,
                        'model_id': 'eleven_monolingual_v1',
                        'voice_settings': settings
                    }

                    response = requests.post(url, headers=headers, params=params, json=payload)
                    if response.status_code == 200:
                        out_file = os.path.join(batch_dir, f'{name}_take_{take}.mp3')
                        with open(out_file, 'wb') as audio_f:
                            audio_f.write(response.content)
                        print(f'Saved to {out_file}')
                        # Persist take record in DB
                        session.add(Take(
                            batch_fk=batch_obj.id,
                            line_name=name,
                            take_number=take,
                            file_path=out_file,
                            stability=stability,
                            similarity=similarity_boost,
                            style=style,
                            speed=speed,
                            speaker_boost=settings['use_speaker_boost']
                        ))
                        session.commit()
                        # Record metadata for this take
                        metadata.append({
                            'file': os.path.basename(out_file),
                            'function': name,
                            'take': take,
                            'settings': settings
                        })
                    else:
                        print(f'Error ({response.status_code}) for {name}, take {take}: {response.text}')
        # After generating all takes for this voice batch, write metadata file
        meta_path = os.path.join(batch_dir, 'metadata.json')
        with open(meta_path, 'w', encoding='utf-8') as meta_f:
            json.dump(metadata, meta_f, indent=2)
        # Update batch status to 'ready'
        batch_obj.status = 'ready'
        session.commit()

    # Close DB session
    session.close()

if __name__ == '__main__':
    main() 