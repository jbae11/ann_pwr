from distutils.core import setup


VERSION = '0.0.1'
setup_kwargs = {
    "version": VERSION,
    "description": 'Saltproc Reactor',
    "author": 'Jin Whan Bae',
    }

if __name__ == '__main__':
    setup(
        name='saltproc_reactor',
        packages=["saltproc_reactor"],
        **setup_kwargs
        )
