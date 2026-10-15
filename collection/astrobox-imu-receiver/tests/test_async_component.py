import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('abi',Path(__file__).resolve().parents[1]/'tools/check_async_component.py')
abi=importlib.util.module_from_spec(spec);spec.loader.exec_module(abi)
def u(n):
    result=[]
    while True:
        b=n&127;n>>=7;result.append(b|(128 if n else 0))
        if not n:return bytes(result)
def section(kind,payload):return bytes([kind])+u(len(payload))+payload
def fixture(names,extra=b''):
    exports=u(len(names))+b''.join(u(len(n.encode()))+n.encode()+b'\0\0' for n in names)
    return abi.COMPONENT+section(1,abi.CORE+section(7,exports)+extra)
def expected():
    return [prefix+abi.PREFIX+m for prefix in ['[async-lift]','[callback][async-lift]'] for m in abi.METHODS]

class AsyncComponent(unittest.TestCase):
    def test_explicit_tasks_for_all_four_callbacks(self):
        self.assertEqual(len(abi.check_async_component(fixture(expected()))['task_entries']),4)
    def test_sync_callbacks_or_missing_completion_callback_are_rejected(self):
        for names in [[abi.PREFIX+m for m in abi.METHODS],expected()[:-1]]:
            with self.assertRaises(ValueError):abi.check_async_component(fixture(names))
    def test_names_in_a_custom_data_section_do_not_count_as_exports(self):
        with self.assertRaises(ValueError):abi.check_async_component(fixture([],section(0,b'\0'+','.join(expected()).encode())))
    def test_truncation_is_rejected(self):
        with self.assertRaises(ValueError):abi.check_async_component(fixture(expected())[:-1])

if __name__=='__main__':unittest.main()
