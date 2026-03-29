def maybe_retry_with_different_cookies(
    *,
    user_id: int,
    url: str,
    result,
    did_cookie_retry: bool,
    is_youtube_url,
    retry_download_with_different_cookies,
    download_fn,
    download_args: tuple,
    logger,
    media_label: str,
):
    if result is not None or not is_youtube_url(url) or did_cookie_retry:
        return result, did_cookie_retry

    logger.info(f"{media_label} download failed for user {user_id}, attempting automatic cookie retry")
    retry_result = retry_download_with_different_cookies(
        user_id, url, download_fn, *download_args
    )

    if retry_result is not None:
        logger.info(f"{media_label} download retry with different cookies successful for user {user_id}")
        return retry_result, True

    logger.warning(f"All cookie retry attempts failed for user {user_id}")
    return result, True


def maybe_retry_with_proxy_on_geo_error(
    *,
    user_id: int,
    url: str,
    error_text: str,
    did_proxy_retry: bool,
    is_youtube_url,
    is_youtube_geo_error,
    retry_download_with_proxy,
    download_fn,
    download_args: tuple,
    logger,
    success_log_text: str,
    failure_log_text: str,
):
    if not is_youtube_url(url) or did_proxy_retry or not is_youtube_geo_error(error_text):
        return None, did_proxy_retry

    logger.info(f"YouTube geo-blocked error detected for user {user_id}, attempting retry with proxy")
    retry_result = retry_download_with_proxy(
        user_id, url, download_fn, *download_args
    )

    if retry_result is not None:
        logger.info(success_log_text.format(user_id=user_id))
        return retry_result, True

    logger.warning(failure_log_text.format(user_id=user_id))
    return None, True
