
pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
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
                bat 'python -m py_compile app.py test_app.py healthcheck.py docker_health_status.py'
            }
        }

        stage('Smoke Tests') {
            steps {
                bat 'python -m unittest -v test_app.py'
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    env.GIT_SHA = bat(
                        script: '@git rev-parse --short=12 HEAD',
                        returnStdout: true
                    ).trim()

                    env.RELEASE_IMAGE =
                        "dfarming-app:${env.GIT_SHA}-${env.BUILD_NUMBER}"

                    env.CI_CONTAINER =
                        "dfarming-ci-${env.BUILD_NUMBER}"
                }

                bat '''
                    docker build -t %CI_IMAGE% -t %RELEASE_IMAGE% .
                    if errorlevel 1 exit /b 1

                    echo Release image: %RELEASE_IMAGE%
                    docker image inspect %RELEASE_IMAGE% --format "Image ID={{.Id}} Created={{.Created}}"
                    if errorlevel 1 exit /b 1
                '''
            }
        }

        stage('Docker Container Health Check') {
            steps {
                bat '''
                    docker run -d --name %CI_CONTAINER% -p 127.0.0.1:5056:5000 -e SECRET_KEY=temporary-ci-test-key -e DATABASE_PATH=/tmp/dfarming-ci-test.db -e UPLOAD_FOLDER=/tmp/dfarming-ci-uploads %RELEASE_IMAGE%
                    if errorlevel 1 exit /b 1

                    python healthcheck.py
                    if errorlevel 1 (
                        docker logs %CI_CONTAINER%
                        exit /b 1
                    )

                    python docker_health_status.py %CI_CONTAINER%
                    if errorlevel 1 exit /b 1
                '''
            }
        }
    }

    post {
        always {
            script {
                if (env.CI_CONTAINER) {
                    bat 'docker rm -f %CI_CONTAINER% 2>NUL & exit /b 0'
                }
            }
        }

        success {
            echo 'D-Farming CI passed: dependencies, syntax, tests, Docker build, and Docker health status.'
            echo "Release image: ${env.RELEASE_IMAGE}"
        }

        failure {
            echo 'D-Farming CI failed. Review the stage logs.'
        }
    }
}
