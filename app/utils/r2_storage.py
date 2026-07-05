"""
Cloudflare R2 клиент за снимките към тестови въпроси.

R2 е S3-compatible обектно хранилище — ползваме boto3 със custom endpoint.
Всички настройки идват от Railway environment variables:

    R2_ACCOUNT_ID          - Cloudflare Account ID
    R2_ACCESS_KEY_ID       - от R2 API токена
    R2_SECRET_ACCESS_KEY   - от R2 API токена
    R2_BUCKET_NAME         - напр. "marad-test"
    R2_PUBLIC_URL          - публичният r2.dev адрес (или custom domain по-късно),
                             напр. "https://pub-xxxxxxxx.r2.dev"

Ако тези променливи липсват (напр. локална разработка без R2 достъп),
is_r2_configured() връща False и images.py пада обратно на Postgres
хранилището — без да чупи нищо, докато R2 setup-ът не е завършен.
"""
import os

_client = None


def is_r2_configured():
    return all([
        os.environ.get('R2_ACCOUNT_ID'),
        os.environ.get('R2_ACCESS_KEY_ID'),
        os.environ.get('R2_SECRET_ACCESS_KEY'),
        os.environ.get('R2_BUCKET_NAME'),
        os.environ.get('R2_PUBLIC_URL'),
    ])


def _get_client():
    global _client
    if _client is None:
        import boto3
        account_id = os.environ['R2_ACCOUNT_ID']
        _client = boto3.client(
            's3',
            endpoint_url=f'https://{account_id}.r2.cloudflarestorage.com',
            aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],
            aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'],
            region_name='auto',
        )
    return _client


def _bucket():
    return os.environ['R2_BUCKET_NAME']


def _key_for(test_id, question_id, fmt):
    return f"tests/{test_id}/questions/{question_id}.{fmt}"


def upload_image(test_id, question_id, img_bytes, fmt):
    """Качва снимка в R2. Връща публичния URL."""
    key = _key_for(test_id, question_id, fmt)
    mimetype = 'image/png' if fmt == 'png' else 'image/jpeg'
    client = _get_client()
    client.put_object(
        Bucket=_bucket(),
        Key=key,
        Body=img_bytes,
        ContentType=mimetype,
        CacheControl='public, max-age=2592000',  # 30 дни
    )
    return public_url_for(key)


def delete_image(test_id, question_id, fmt):
    key = _key_for(test_id, question_id, fmt)
    client = _get_client()
    client.delete_object(Bucket=_bucket(), Key=key)


def delete_all_for_test(test_id, question_ids_formats):
    """question_ids_formats: списък от (question_id, format) двойки."""
    client = _get_client()
    objects = [{'Key': _key_for(test_id, qid, fmt)} for qid, fmt in question_ids_formats]
    if not objects:
        return
    # delete_objects приема максимум 1000 наведнъж
    for i in range(0, len(objects), 1000):
        client.delete_objects(Bucket=_bucket(), Delete={'Objects': objects[i:i+1000]})


def public_url_for(key):
    base = os.environ['R2_PUBLIC_URL'].rstrip('/')
    return f"{base}/{key}"


def public_url_for_image(test_id, question_id, fmt):
    return public_url_for(_key_for(test_id, question_id, fmt))
