from setuptools import setup, find_packages
setup(
    name='sdp-api',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'fastapi',
        'uvicorn',
        'sqlalchemy',
        'pydantic',
        'pydantic[email]',
        'python-jose',
       'passlib',
       'pydantic-settings',
        'python-multipart',
        # aggiungi altre dipendenze qui
    ],
    entry_points={
        'console_scripts': [
            'start-api=nome_tuo_backend.main:app',
        ],
    },
    python_requires='>=3.11.8',
)