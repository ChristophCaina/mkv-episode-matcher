# episode_matcher.py
import os
from concurrent.futures import ThreadPoolExecutor
from mkv_episode_matcher.config import get_config
from mkv_episode_matcher.tmdb_client import fetch_show_id
from mkv_episode_matcher.utils import load_show_hashes, find_matching_episode, rename_episode_file, check_filename,preprocess_hashes
from loguru import logger
from mkv_episode_matcher.__main__ import CONFIG_FILE
@logger.catch
def process_show(season=None,force=False,dry_run=False):
    """
    Process the show by downloading episode images and finding matching episodes.

    Args:
        api_key (str): The TMDb API key.
        show_dir (str): The main directory of the show.
    """
    config = get_config(CONFIG_FILE)
    api_key = config.get("api_key")
    show_dir = config.get("show_dir")
    show_name = os.path.basename(show_dir)
    logger.info(f"Processing show '{show_name}'...")
    show_id = fetch_show_id(show_name)
    if show_id is None:
        logger.error(f"Could not find show '{os.path.basename(show_dir)}' on TMDb.")
        return

    season_paths = [os.path.join(show_dir, d) for d in os.listdir(show_dir) if os.path.isdir(os.path.join(show_dir, d))]
    logger.info(f"Found {len(season_paths)} seasons for show '{os.path.basename(show_dir)}'")
    seasons_to_process = [int(os.path.basename(season_path).split()[-1]) for season_path in season_paths]
    show_hashes = preprocess_hashes(show_name,show_id,seasons_to_process)

    with ThreadPoolExecutor() as executor:
        if isinstance(season, int):
            # If a season number is provided then just process that one season
            for season_path in season_paths:
                season_number = int(os.path.basename(season_path).split()[-1])
                if season_number == season:
                    try:
                        # Attempt to get hash from show_hashes and process the season
                        executor.submit(process_season, show_id, season_number, season_path,show_hashes[str(season_number)])
                    except KeyError:
                        # If a KeyError is raised then skip this season
                        logger.warning(f"Season {season} not found in show_hashes")
                else:
                    executor.submit(process_season, show_id, season_number, season_path,show_hashes[str(season_number)])
        else:
            # Otherwise process all seasons available
            
            for season_path in season_paths:
                season_number = int(os.path.basename(season_path).split()[-1])
                try:
                    # Attempt to get hash from show_hashes and process the season
                    executor.submit(process_season, show_id, season_number, season_path,show_hashes[str(season_number)])
                except KeyError:
                    # If a KeyError is raised then skip this season
                    logger.warning(f"Season {season} not found in show_hashes")

    logger.info(f"Show '{os.path.basename(show_dir)}' processing completed")

@logger.catch
def process_season(show_id, season_number, season_path,season_hashes,force=False,dry_run=False):
    """
    Process a single season by downloading episode images and finding matching episodes.

    Args:
        show_id (str): The TMDb ID of the show.
        season_number (int): The season number.
        season_path (str): The path to the season directory.
    """
    logger.info(f"Processing Season {season_number}...")
    config = get_config(CONFIG_FILE)
    show_dir = config.get("show_dir")
    show_name =os.path.basename(show_dir)
    n_episodes = len(season_hashes.keys())
    matching_episodes = {}

    mkv_files = [os.path.join(season_path, f) for f in os.listdir(season_path) if f.endswith(".mkv")]
    for file in mkv_files:
        logger.info(f'Processing {os.path.basename(file)}')
        for i in range(n_episodes):
            already_renamed = check_filename(os.path.basename(file),show_name,season_number,i)
            if already_renamed:
                logger.info(f'{os.path.basename(file)} already processed. Skipping...')
                break
        if already_renamed:
            continue
        filepath = os.path.join(season_path, file)
        episode = find_matching_episode(filepath, season_path, season_number, season_hashes)
        if episode is not None:
            matching_episodes[file] = episode
            if dry_run:
                logger.info('Skipping renaming of {os.path.basename(file)} with episode {episode}')
            else:
                rename_episode_file(filepath,season_number,episode)
        else:
            logger.warning(f'Unable to determine episode number for {os.path.basename(file)}')