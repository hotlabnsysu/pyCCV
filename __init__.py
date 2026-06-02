# pyCCV
# Python PIV 分析工具

__version__ = "2.0.0"
__author__ = "pyCCV"

# 延遲載入以避免循環 import
def __getattr__(name):
    if name == "piv_fft_multi":
        from .core.piv_fft import piv_fft_multi
        return piv_fft_multi
    elif name == "post_process":
        from .core.postprocess import post_process
        return post_process
    elif name == "file_checker":
        from .utils.file_checker import file_checker
        return file_checker
    raise AttributeError(f"模組 'pyCCV' 沒有屬性 '{name}'")
