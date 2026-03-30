# --- receiving formats and metadata via yt-dlp ---
from dataclasses import dataclass
import os
import yt_dlp
from CONFIG.config import Config
from CONFIG.messages import Messages, safe_get_messages
from HELPERS.logger import logger, send_error_to_user
from HELPERS.filesystem_hlp import create_directory
from URL_PARSERS.nocookie import is_no_cookie_domain
from URL_PARSERS.youtube import is_youtube_url
from URL_PARSERS.filter_check import is_no_filter_domain
from URL_PARSERS.filter_utils import create_smart_match_filter, create_legacy_match_filter
from HELPERS.pot_helper import add_pot_to_ytdl_opts
from CONFIG.limits import LimitsConfig
from HELPERS.fallback_helper import should_fallback_to_gallery_dl


@dataclass(frozen=True)
class FormatExtractionPolicy:
    cookie_file: str | None
    use_proxy: bool


def _resolve_format_download_error(
    *,
    error_text: str,
    url: str,
    user_id: int | None,
    extract_info_operation,
    opts: dict,
):
    if "LIVE_STREAM_DETECTED" in error_text and LimitsConfig.ENABLE_LIVE_STREAM_BLOCKING:
        return {'error': 'LIVE_STREAM_DETECTED'}

    if is_youtube_url(url) and user_id is not None:
        from COMMANDS.cookies_cmd import is_youtube_cookie_error, retry_download_with_different_cookies

        if is_youtube_cookie_error(error_text):
            logger.info(
                f"YouTube cookie error detected in get_video_formats for user {user_id}, "
                "attempting automatic retry"
            )
            retry_result = retry_download_with_different_cookies(
                user_id, url, extract_info_operation, opts
            )
            if retry_result is not None:
                logger.info(f"get_video_formats retry with different cookies successful for user {user_id}")
                return retry_result
            logger.warning(f"All cookie retry attempts failed in get_video_formats for user {user_id}")
    elif not is_youtube_url(url) and user_id is not None:
        logger.info(
            f"Non-YouTube error detected in get_video_formats for user {user_id}, "
            "attempting cookie fallback"
        )
        error_str = error_text.lower()
        if any(keyword in error_str for keyword in ['cookie', 'auth', 'login', 'sign in', '403', '401', 'forbidden', 'unauthorized']):
            logger.info(f"Error appears to be cookie-related for {url}, trying cookie fallback")
            from COMMANDS.cookies_cmd import try_non_youtube_cookie_fallback

            retry_result = try_non_youtube_cookie_fallback(
                user_id, url, extract_info_operation, opts
            )
            if retry_result is not None:
                logger.info(f"get_video_formats retry with cookie fallback successful for user {user_id}")
                return retry_result
            logger.warning(f"get_video_formats retry with cookie fallback failed for user {user_id}")
        else:
            logger.info(f"Error appears to be non-cookie-related for {url}, skipping cookie fallback")

    if "tiktok.com" in url.lower() and "private" in error_text.lower() and "account" in error_text.lower():
        logger.info(f"TikTok private account detected for {url}, recommending gallery-dl fallback")
        return {'error': 'TIKTOK_PRIVATE_ACCOUNT', 'original_error': error_text}

    if should_fallback_to_gallery_dl(error_text, url):
        logger.info(f"Fallback to gallery-dl recommended for {url} due to error: {error_text[:200]}...")
        return {'error': 'FALLBACK_TO_GALLERY_DL', 'original_error': error_text}

    return None


def _try_restore_youtube_cookie_source(
    *,
    user_id: int,
    url: str,
    user_cookie_path: str,
    cookie_urls: list[str],
    use_unchecked_only: bool,
    log_prefix: str,
) -> str | None:
    from COMMANDS.cookies_cmd import (
        _download_content,
        get_unchecked_cookie_sources,
        mark_cookie_source_checked,
        test_youtube_cookies_on_url,
    )

    candidate_indices = (
        get_unchecked_cookie_sources(user_id, cookie_urls)
        if use_unchecked_only
        else list(range(len(cookie_urls)))
    )
    if not candidate_indices:
        logger.warning(f"All cookie sources have been checked for user {user_id}, no more sources to try")
        return None

    for idx in candidate_indices:
        cookie_url = cookie_urls[idx]
        logger.info(f"{log_prefix} {idx + 1} for format detection for user {user_id}")
        if use_unchecked_only:
            mark_cookie_source_checked(user_id, idx)
        try:
            ok, status_code, content, error = _download_content(cookie_url, user_id=user_id)
        except Exception as download_e:
            logger.error(f"Error processing cookie source {idx + 1} for user {user_id}: {download_e}")
            continue
        if ok and content and len(content) <= 100 * 1024:
            with open(user_cookie_path, "wb") as cf:
                cf.write(content)
            if test_youtube_cookies_on_url(user_cookie_path, url, user_id):
                logger.info(
                    f"YouTube cookies from source {idx + 1} work on user's URL for format detection "
                    f"for user {user_id} - saved to user folder"
                )
                return user_cookie_path
            logger.warning(
                f"YouTube cookies from source {idx + 1} don't work on user's URL for format "
                f"detection for user {user_id}"
            )
            if os.path.exists(user_cookie_path):
                os.remove(user_cookie_path)
        else:
            logger.warning(
                f"Failed to download YouTube cookies from source {idx + 1} for format detection "
                f"for user {user_id}"
            )
    return None


def _resolve_format_detection_cookie_file(
    *,
    url: str,
    user_id: int,
    user_cookie_path: str,
    cookies_already_checked: bool,
) -> str | None:
    if is_youtube_url(url):
        from COMMANDS.cookies_cmd import get_youtube_cookie_urls, test_youtube_cookies_on_url

        if not cookies_already_checked:
            if os.path.exists(user_cookie_path):
                logger.info(
                    safe_get_messages(user_id).YTDLP_CHECKING_EXISTING_YOUTUBE_COOKIES_MSG.format(
                        user_id=user_id
                    )
                )
                if test_youtube_cookies_on_url(user_cookie_path, url, user_id):
                    logger.info(
                        safe_get_messages(user_id).YTDLP_EXISTING_YOUTUBE_COOKIES_WORK_MSG.format(
                            user_id=user_id
                        )
                    )
                    return user_cookie_path
                logger.info(
                    safe_get_messages(user_id).YTDLP_EXISTING_YOUTUBE_COOKIES_FAILED_MSG.format(
                        user_id=user_id
                    )
                )
            else:
                logger.info(
                    safe_get_messages(user_id).YTDLP_NO_YOUTUBE_COOKIES_FOUND_MSG.format(
                        user_id=user_id
                    )
                )

            cookie_urls = get_youtube_cookie_urls()
            if not cookie_urls:
                logger.warning(
                    safe_get_messages(user_id).YTDLP_NO_YOUTUBE_COOKIE_SOURCES_CONFIGURED_MSG.format(
                        user_id=user_id
                    )
                )
                return None
            restored_cookie = _try_restore_youtube_cookie_source(
                user_id=user_id,
                url=url,
                user_cookie_path=user_cookie_path,
                cookie_urls=cookie_urls,
                use_unchecked_only=True,
                log_prefix="Trying YouTube cookie source",
            )
            if restored_cookie:
                return restored_cookie
            logger.warning(
                safe_get_messages(user_id).YTDLP_ALL_YOUTUBE_COOKIE_SOURCES_FAILED_MSG.format(
                    user_id=user_id
                )
            )
            return None

        if os.path.exists(user_cookie_path):
            logger.info(
                safe_get_messages(user_id).YTDLP_USING_YOUTUBE_COOKIES_ALREADY_VALIDATED_MSG.format(
                    user_id=user_id
                )
            )
            return user_cookie_path

        logger.info(
            safe_get_messages(user_id).YTDLP_NO_YOUTUBE_COOKIES_FOUND_ATTEMPTING_RESTORE_MSG.format(
                user_id=user_id
            )
        )
        cookie_urls = get_youtube_cookie_urls()
        if not cookie_urls:
            logger.warning(
                f"No YouTube cookie sources configured for format detection for user {user_id}, "
                "will try without cookies"
            )
            return None
        restored_cookie = _try_restore_youtube_cookie_source(
            user_id=user_id,
            url=url,
            user_cookie_path=user_cookie_path,
            cookie_urls=cookie_urls,
            use_unchecked_only=False,
            log_prefix="Trying YouTube cookie source",
        )
        if restored_cookie:
            return restored_cookie
        logger.warning(
            f"All YouTube cookie sources failed for format detection for user {user_id}, "
            "will try without cookies"
        )
        return None

    from COMMANDS.cookies_cmd import get_cookie_cache_result

    cache_result = get_cookie_cache_result(user_id, url)
    if cache_result and cache_result['result']:
        logger.info(f"Using cached cookies for non-YouTube format detection: {url}")
        return cache_result['cookie_path']
    if os.path.exists(user_cookie_path):
        logger.info(f"Using user cookies for non-YouTube format detection: {url}")
        return user_cookie_path
    logger.info(f"No user cookies found for non-YouTube format detection: {url}, will try fallback")
    return None


def _apply_format_detection_proxy_policy(
    *,
    ytdl_opts: dict,
    url: str,
    user_id: int,
    use_proxy: bool,
) -> dict:
    if use_proxy:
        from COMMANDS.proxy_cmd import get_proxy_config

        proxy_config = get_proxy_config()
        if proxy_config and 'type' in proxy_config and 'ip' in proxy_config and 'port' in proxy_config:
            if proxy_config['type'] == 'http':
                if proxy_config.get('user') and proxy_config.get('password'):
                    proxy_url = f"http://{proxy_config['user']}:{proxy_config['password']}@{proxy_config['ip']}:{proxy_config['port']}"
                else:
                    proxy_url = f"http://{proxy_config['ip']}:{proxy_config['port']}"
            elif proxy_config['type'] == 'https':
                if proxy_config.get('user') and proxy_config.get('password'):
                    proxy_url = f"https://{proxy_config['user']}:{proxy_config['password']}@{proxy_config['ip']}:{proxy_config['port']}"
                else:
                    proxy_url = f"https://{proxy_config['ip']}:{proxy_config['port']}"
            elif proxy_config['type'] in ['socks4', 'socks5', 'socks5h']:
                if proxy_config.get('user') and proxy_config.get('password'):
                    proxy_url = f"{proxy_config['type']}://{proxy_config['user']}:{proxy_config['password']}@{proxy_config['ip']}:{proxy_config['port']}"
                else:
                    proxy_url = f"{proxy_config['type']}://{proxy_config['ip']}:{proxy_config['port']}"
            else:
                if proxy_config.get('user') and proxy_config.get('password'):
                    proxy_url = f"http://{proxy_config['user']}:{proxy_config['password']}@{proxy_config['ip']}:{proxy_config['port']}"
                else:
                    proxy_url = f"http://{proxy_config['ip']}:{proxy_config['port']}"
            ytdl_opts['proxy'] = proxy_url
            logger.info(f"Force using proxy for format detection: {proxy_url}")
        else:
            logger.warning("Proxy requested but proxy configuration is incomplete")
        return ytdl_opts

    from HELPERS.proxy_helper import add_proxy_to_ytdl_opts

    return add_proxy_to_ytdl_opts(ytdl_opts, url, user_id)

def get_video_formats(url, user_id=None, playlist_start_index=1, cookies_already_checked=False, use_proxy=False, playlist_end_index=None):
    # Detailed debug logging
    logger.info("🔍 [DEBUG] get_video_formats called with parameters:")
    logger.info(f"   url: {url}")
    logger.info(f"   user_id: {user_id}")
    logger.info(f"   playlist_start_index: {playlist_start_index}")
    logger.info(f"   playlist_end_index: {playlist_end_index}")
    logger.info(f"   cookies_already_checked: {cookies_already_checked}")
    logger.info(f"   use_proxy: {use_proxy}")
    
    # Reset the "checked cookie sources" cache for a new task
    if user_id is not None:
        from COMMANDS.cookies_cmd import reset_checked_cookie_sources
        reset_checked_cookie_sources(user_id)
        logger.info(f"🔄 [DEBUG] Reset checked cookie sources for new task for user {user_id}")
    
    messages = safe_get_messages(user_id)
    
    # Build playlist_items taking the range into account
    if playlist_end_index is not None and playlist_end_index != playlist_start_index:
        # For ranges, use START:END or START:END:-1 for reverse order
        if playlist_start_index < 0 or playlist_end_index < 0:
            # For negative indices determine reverse order
            is_reverse = (playlist_start_index < 0 and playlist_end_index < 0 and abs(playlist_start_index) < abs(playlist_end_index)) or (playlist_start_index > playlist_end_index)
            if is_reverse:
                playlist_items_str = f"{playlist_start_index}:{playlist_end_index}:-1"
            else:
                playlist_items_str = f"{playlist_start_index}:{playlist_end_index}"
        elif playlist_start_index > playlist_end_index:
            # Reverse order with positive indices
            playlist_items_str = f"{playlist_start_index}:{playlist_end_index}:-1"
        else:
            # Forward order
            playlist_items_str = f"{playlist_start_index}:{playlist_end_index}"
    else:
        # Single item
        playlist_items_str = str(playlist_start_index)
    
    ytdl_opts = {
        'quiet': True,
        'skip_download': True,
        'forcejson': True,
        'no_warnings': True,
        'extract_flat': False,
        'simulate': True,
        'playlist_items': playlist_items_str,    
        'extractor_args': {
            'generic': {
                'impersonate': ['chrome']
            },
            'youtubetab': {
                'skip': ['authcheck']
            }
        },
        'referer': url,
        'geo_bypass': True,
        'check_certificate': False,
        'live_from_start': True
    }
    
    # Add match_filter only if domain is not in NO_FILTER_DOMAINS
    if not is_no_filter_domain(url):
        # Use smart filter that allows downloads when duration is unknown
        ytdl_opts['match_filter'] = create_smart_match_filter()
    else:
        logger.info(safe_get_messages(user_id).YTDLP_SKIPPING_MATCH_FILTER_MSG.format(url=url))
    
    # Add user's custom yt-dlp arguments (but exclude format to get all available formats)
    if user_id is not None:
        from COMMANDS.args_cmd import get_user_ytdlp_args, log_ytdlp_options
        user_args = get_user_ytdlp_args(user_id, url)
        if user_args:
            # Remove format parameter to get all available formats
            user_args_copy = user_args.copy()
            user_args_copy.pop('format', None)
            ytdl_opts.update(user_args_copy)
        
        # Log final yt-dlp options for debugging
        log_ytdlp_options(user_id, ytdl_opts, "get_video_formats")
    
    if user_id is not None:
        user_dir = os.path.join("users", str(user_id))
        # Check the availability of cookie.txt in the user folder
        user_cookie_path = os.path.join(user_dir, "cookie.txt")
        cookie_file = _resolve_format_detection_cookie_file(
            url=url,
            user_id=user_id,
            user_cookie_path=user_cookie_path,
            cookies_already_checked=cookies_already_checked,
        )
        
        # We check whether to use —no-Cookies for this domain
        if is_no_cookie_domain(url):
            ytdl_opts['cookiefile'] = None  # Equivalent-No-Cookies
            logger.info(safe_get_messages(user_id).YTDLP_USING_NO_COOKIES_FOR_DOMAIN_MSG.format(url=url))
        elif cookie_file:
            ytdl_opts['cookiefile'] = cookie_file
            logger.info(f"[YTDLP DEBUG] Using cookies for {url}: {cookie_file}")
        else:
            logger.info(f"[YTDLP DEBUG] No cookies available for {url}")
        
        # Add proxy configuration if needed for this domain 
        ytdl_opts = _apply_format_detection_proxy_policy(
            ytdl_opts=ytdl_opts,
            url=url,
            user_id=user_id,
            use_proxy=use_proxy,
        )
    
    # Add PO token provider for YouTube domains
    ytdl_opts = add_pot_to_ytdl_opts(ytdl_opts, url)
    
    # Try with proxy fallback if user proxy is enabled
    def extract_info_operation(opts):
        try:
            logger.info("🔍 [DEBUG] extract_info_operation: starting extraction")
            logger.info(f"   url: {url}")
            logger.info(f"   opts keys: {list(opts.keys())}")
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            
            logger.info("✅ [DEBUG] extract_info_operation: extraction finished")
            logger.info(f"   info type: {type(info)}")
            if isinstance(info, dict):
                logger.info(f"   info keys: {list(info.keys())}")
                if 'duration' in info:
                    logger.info(f"   duration: {info['duration']} (type: {type(info['duration'])})")
                if 'is_live' in info:
                    logger.info(f"   is_live: {info['is_live']} (type: {type(info['is_live'])})")
            
            # Normalize info to a dict
            # For playlists, keep all entries to download thumbnails/covers
            playlist_entries = None
            if isinstance(info, list):
                info = (info[0] if len(info) > 0 else {})
                logger.info("🔍 [DEBUG] info was a list; using the first element")
            elif isinstance(info, dict) and 'entries' in info:
                entries = info.get('entries')
                if isinstance(entries, list) and len(entries) > 0:
                    # Keep all entries for thumbnail/cover downloads
                    playlist_entries = entries
                    info = entries[0]
                    logger.info(f"🔍 [DEBUG] info contained entries; using the first element. Total entries: {len(entries)}")
                    # Attach entries for ask_quality_menu
                    info['_playlist_entries'] = playlist_entries
            
            # Check for live stream after extraction (only if detection is enabled)
            if info and info.get('is_live', False) and LimitsConfig.ENABLE_LIVE_STREAM_BLOCKING:
                logger.warning(f"Live stream detected in get_video_formats: {url}")
                return {'error': 'LIVE_STREAM_DETECTED'}
            
            # Cache successful cookie result for future use
            if not is_youtube_url(url) and user_id is not None:
                from COMMANDS.cookies_cmd import set_cookie_cache_result
                cookie_file_path = opts.get('cookiefile')
                if cookie_file_path and os.path.exists(cookie_file_path):
                    set_cookie_cache_result(user_id, url, True, cookie_file_path)
                    logger.info(f"Cached successful cookie result for format detection {url}")
            
            logger.info("✅ [DEBUG] extract_info_operation: returning info")
            return info
        except yt_dlp.utils.DownloadError as e:
            error_text = str(e)
            logger.error(f"DownloadError in get_video_formats: {error_text}")
            resolved_error = _resolve_format_download_error(
                error_text=error_text,
                url=url,
                user_id=user_id,
                extract_info_operation=extract_info_operation,
                opts=opts,
            )
            if resolved_error is not None:
                return resolved_error
            raise e
        except Exception as e:
            logger.error(f"Error extracting info for {url}: {e}")
            raise e
    
    from HELPERS.proxy_helper import try_with_proxy_fallback
    result = try_with_proxy_fallback(ytdl_opts, url, user_id, extract_info_operation)
    if result is None:
        return {'error': 'Failed to extract video information with all available proxies'}
    return result


# YT-DLP HOOK

def ytdlp_hook(d):
    logger.info(d['status'])
