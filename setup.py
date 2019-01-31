from distutils.core import setup


VERSION = '0.0.1'
setup_kwargs = {
    "version": VERSION,
    "description": 'ANN LWR',
    "author": 'Jin Whan Bae',
    }

if __name__ == '__main__':
    setup(
        name='ann_lwr',
        packages=["ann_lwr"],
        **setup_kwargs
        )
