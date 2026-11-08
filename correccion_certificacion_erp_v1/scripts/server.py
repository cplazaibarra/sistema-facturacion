import os
from pathlib import Path
from core.test_database_guard import assert_current_test_database_authorized
assert_current_test_database_authorized()
from app import app
assert str(Path(app.root_path).resolve())==str(Path(os.environ['CERTIFICATION_WORK']).resolve())
app.config.update(TESTING=True,PROPAGATE_EXCEPTIONS=False)
app.run(host='127.0.0.1',port=15021,use_reloader=False,debug=False,threaded=True)
