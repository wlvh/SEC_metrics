"""Explicit original-image-metadata successor; shared defaults are unchanged."""
from .c02_table_development_input import prepare_ordinary_table_development_input
from .c02_image_context_c294b12f import augment_request
from .continuous_request_context import measure_request


def prepare_ordinary_image_development_input(*, data_root, company_id, task_text):
    prepared = prepare_ordinary_table_development_input(
        data_root=data_root,company_id=company_id,task_text=task_text)
    body, view, images = augment_request(prepared['request_body'],prepared['raw_source'],
        prepared['table_grid'],prepared['document']['raw_asset_id'])
    return {**prepared,'base_table_view':prepared['view'],'view':view,
        'original_image_markup':images,'request_body':body,
        'measurement':measure_request(body,require_reference=True)}
