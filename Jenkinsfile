pipeline {
    agent any

    options {
        timestamps()
    }

    environment {
        CI_IMAGE = 'dfarming-app:ci'
    }

    stages {
        stage('Install Python Dependencies') {
            steps {
                bat 'python -m pip install -r requirements.txt'
            }
        }

        stage('Python Syntax Check') {
            steps {
                bat 'python -m py_compile app.py test_app.py'
            }
        }

        stage('Smoke Tests') {
            steps {
                bat 'python -m unittest -v test_app.py'
            }
        }

        stage('Build Docker Image') {
            steps {
                bat 'docker build -t %CI_IMAGE% .'
            }
        }
    }

    post {
        success {
            echo 'D-Farming CI passed: dependencies, syntax, tests, and Docker build.'
        }
        failure {
            echo 'D-Farming CI failed. Review the stage logs.'
        }
    }
}
