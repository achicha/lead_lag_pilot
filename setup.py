from setuptools import setup
from Cython.Build import cythonize

setup(name='lead_lag_pilot',
      version='0.1',
      description='Initial lead-lag test',
    #   url='http://github.com/storborg/funniest',
      packages=['strategy'],
      zip_safe=False,
      ext_modules=cythonize(
        module_list=[
            "strategy/strategy.pyx",
        ],
        annotate=True,
        compiler_directives={
            "embedsignature": True,
            "profile": True,
            "linetrace": True,
            "language_level": 3
        }
    )
)
