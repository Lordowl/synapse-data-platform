from setuptools import setup, find_packages

setup(
    name='sdp-api',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    py_modules=['main'],
    install_requires=[
        'fastapi>=0.100.0',
        'uvicorn[standard]>=0.20.0',
        'sqlalchemy>=2.0.0',
        'pydantic>=2.0.0',
        'pydantic[email]>=2.0.0',
        'pydantic-settings>=2.0.0',
        'python-jose[cryptography]>=3.3.0',
        'passlib[bcrypt]>=1.7.4',
        'python-multipart>=0.0.6',
        'bcrypt>=4.0.0',
        'requests>=2.31.0',  # Per il tuo sistema di aggiornamento
    ],
    entry_points={
        'console_scripts': [
            'sdp-api=main:main',
        ],
    },
    python_requires='>=3.11.8',
    author='Your Name',
    author_email='your.email@example.com',
    description='Synapse Data Platform API',
    long_description='API per la Synapse Data Platform.',
    url='https://github.com/Lordowl/synapse-data-platform',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
)