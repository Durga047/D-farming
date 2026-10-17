pipeline {
    agent any

    options {
        timestamps()
    }

    environment {
        CI_IMAGE = 'dfarming-app:ci'
        CI_CONTAINER = 'dfarming-ci-healthcheck'
    }

    stages {
        stage('Install Python Dependencies') {
            steps {
                bat 'python -m pip install -r requirements.txt'
            }
        }

        stage('Python Syntax Check') {
            steps {
                bat 'python -m py_compile app.py test_app.py healthcheck.py'
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

        stage('Docker Container Health Check') {
            steps {
                bat '''
                    docker rm -f %CI_CONTAINER% 2>NUL
                    docker run -d --name %CI_CONTAINER% -p 127.0.0.1:5056:5000 -e SECRET_KEY=temporary-ci-test-key -e DATABASE_PATH=/tmp/dfarming-ci-test.db -e UPLOAD_FOLDER=/tmp/dfarming-ci-uploads %CI_IMAGE%
                    if errorlevel 1 exit /b 1

                    python healthcheck.py
                    if errorlevel 1 (
                        docker logs %CI_CONTAINER%
                        exit /b 1
                    )

                    setlocal EnableDelayedExpansion
                    set "HEALTH_STATUS=starting"

                    for /L %%i in (1,1,25) do (
                        for /F "delims=" %%s in ('docker inspect --format "{{.State.Health.Status}}" %CI_CONTAINER% 2^>NUL') do set "HEALTH_STATUS=%%s"

                        if "!HEALTH_STATUS!"=="healthy" (
                            echo Docker health status is healthy.
                            exit /b 0
                        )

                        if "!HEALTH_STATUS!"=="unhealthy" (
                            echo Docker container reported unhealthy status.
                            docker logs %CI_CONTAINER%
                            exit /b 1
                        )

                        timeout /t 2 /nobreak >NUL
                    )

                    echo Timed out waiting for Docker health status. Current status: !HEALTH_STATUS!
                    docker logs %CI_CONTAINER%
                    exit /b 1
                '''
            }
        }
    }

    post {
        always {
            bat 'docker rm -f %CI_CONTAINER% 2>NUL & exit /b 0'
        }
        success {
            echo 'D-Farming CI passed: dependencies, syntax, tests, Docker build, and Docker health status.'
        }
        failure {
            echo 'D-Farming CI failed. Review the stage logs.'
        }
    }
}
