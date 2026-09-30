"""Fixed-size presentation pagination; exports opt out explicitly in repositories."""
from urllib.parse import urlencode

PAGE_SIZE = 30


def parse_page(value):
    try:
        return max(1, int(value))
    except (TypeError, ValueError, OverflowError):
        return 1


def pagination_meta(total, page=1):
    total = max(0, int(total))
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(parse_page(page), total_pages)
    offset = (page - 1) * PAGE_SIZE
    return dict(total=total, total_count=total, total_pages=total_pages,
                page=page, per_page=PAGE_SIZE, offset=offset,
                start=offset + 1 if total else 0, end=min(offset + PAGE_SIZE, total))


def page_url(page):
    from flask import request
    args = request.args.to_dict(flat=False)
    args.pop('per_page', None)
    args.pop('page_size', None)
    args['page'] = [str(parse_page(page))]
    return request.path + '?' + urlencode(args, doseq=True)
