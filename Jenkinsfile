pipeline {
    agent any

    // Global environment (computed in the pipeline)
    environment {
        IMAGE_TAG = ""
        TEST_IMAGE_TAG = ""
    }

    // Jenkins parameters
    parameters {
        string(name: 'GIT_BRANCH', defaultValue: 'main', description: 'Branch to build')
        string(name: 'GIT_REPO', defaultValue: 'Your GH ssh url', description: 'Git repo URL')
        string(name: 'CREDENTIALS', defaultValue: 'YourJenkinsCredentialsIDHere', description: 'Jenkins Credentials ID')
        string(name: 'IMAGE_BASE', defaultValue: 'your-registry/aspnet-api', description: 'Base name for Docker images (repository/name)')
        string(name: 'SONAR_PROJECT_KEY', defaultValue: 'mobileapi', description: 'SonarQube Project Key (e.g., mobileapi)')
    }

    stages {
        stage('Checkout Source') {
            steps {
                git branch: "${params.GIT_BRANCH}",
                    url: "${params.GIT_REPO}",
                    credentialsId: "${params.CREDENTIALS}"
            }
        }

        stage('Determine Next Image Tag and Build Image') {
            steps {
                script {
                    // Get the highest numeric tag for this IMAGE_BASE (if any)
                    def lastTag = sh(
                        script: "docker image ls --format \"{{.Tag}}\" ${params.IMAGE_BASE} | grep -E \"^[0-9]+$\" | sort -n | tail -1",
                        returnStdout: true
                    ).trim()

                    if (lastTag == "") {
                        env.IMAGE_TAG = "${params.IMAGE_BASE}:1"
                    } else {
                        def next = lastTag.toInteger() + 1
                        env.IMAGE_TAG = "${params.IMAGE_BASE}:${next}"
                    }

                    echo "Using image tag: ${env.IMAGE_TAG}"
                }

                // Build the main application image
                sh "docker build -t ${env.IMAGE_TAG} -f ./Dockerfile ."
            }
        }

        stage('Run Unit Tests') {
            steps {
                script {
                    // Stable tag for the test image
                    env.TEST_IMAGE_TAG = "${params.IMAGE_BASE}.test"
                }

                sh """
                  # Build the test image
                  docker build -t ${env.TEST_IMAGE_TAG} -f ./Dockerfile.test .

                  # Clean and recreate TestResults directory in the workspace
                  rm -rf TestResults
                  mkdir -p TestResults

                  # Run tests in the container, writing JUnit XML into the mounted TestResults directory
                  docker run --rm \\
                    -v \$PWD/TestResults:/src/TestResults \\
                    ${env.TEST_IMAGE_TAG}
                """

                // Publish JUnit test report so Jenkins shows a "Tests" tab/button
                junit 'TestResults/*.xml'
            }
        }

        stage('SonarQube Analysis') {
            steps {
                // Name must match the SonarQube server configuration in Jenkins
                withSonarQubeEnv('My SonarQube') {
                    sh """
                        # Build sonar scan image using Dockerfile.sonar
                        docker build -t ${params.IMAGE_BASE}.sonarscan -f Dockerfile.sonar .

                        # Run sonar analysis inside the container
                        docker run --rm \\
                            -e SONAR_HOST_URL=${SONAR_HOST_URL} \\
                            -e SONAR_PROJECT_KEY=${params.SONAR_PROJECT_KEY} \\
                            -e SONAR_TOKEN=${SONAR_AUTH_TOKEN} \\
                            ${params.IMAGE_BASE}.sonarscan
                    """
                }
            }
        }

        // Only enforce Quality Gate for main branch
        stage('Quality Gate') {
            when { branch 'main' }  // Feature branches still run analysis, but don't enforce gates
            steps {
                timeout(time: 10, unit: 'MINUTES') {
                    script {
                        def qg = waitForQualityGate()
                        echo "Quality Gate status: ${qg.status}"
                        if (qg.status != 'OK') {
                            unstable "Build marked UNSTABLE due to Quality Gate: ${qg.status}"
                        }
                    }
                }
            }
        }

        // Only deploy when building from main branch
        stage('Deploy Stack') {
            when { branch 'main' }  // Prevents deployment from feature/test branches
            steps {
                sh 'docker compose down || true'
                sh "IMAGE_TAG=${env.IMAGE_TAG} docker compose up -d"
            }
        }

        stage('Build & Publish Docs') {
            steps {
                // Build API docs from XML comments using DocFX inside a .NET SDK container
                sh """
                  docker run --rm \\
                    -v \$PWD:/work \\
                    -w /work \\
                    mcr.microsoft.com/dotnet/sdk:8.0 \\
                    bash -c '
                      # Build the project so XML docs are generated
                      dotnet build MobileAPI/MobileAPI.csproj -c Release

                      # Install DocFX as a dotnet global tool
                      dotnet tool install -g docfx || true

                      export PATH="\\\$PATH:/root/.dotnet/tools"

                      # Generate documentation as defined in docfx.json
                      docfx docfx.json
                    '
                """

                // Publish generated HTML docs so Jenkins shows an "API Documentation" link
                publishHTML(target: [
                    reportName           : 'API Documentation',
                    reportDir            : 'docs/_site',
                    reportFiles          : 'index.html',
                    keepAll              : true,
                    alwaysLinkToLastBuild: true,
                    allowMissing         : true
                ])
            }
        }

        // This requires a one-time setup in GH:
        // Go to your repo on GitHub → Settings → Pages
        // Under Source:
        //    Choose Branch: gh-pages
        //    Choose Folder: / (root)
        //    Save.
        stage('Publish GitHub Pages') {
            when { branch 'main' } // Only publish docs for main branch builds
            steps {
                // Use the same SSH credentials used for checkout
                sshagent (credentials: [params.CREDENTIALS]) {
                    sh """
                      # Fresh clone of gh-pages branch into a separate folder
                      rm -rf gh-pages
        
                      # Try to clone gh-pages; if it doesn't exist, create it as an orphan branch
                      git clone --branch gh-pages --single-branch ${params.GIT_REPO} gh-pages || \
                      (git clone ${params.GIT_REPO} gh-pages && cd gh-pages && git checkout --orphan gh-pages)
        
                      cd gh-pages
        
                      # Remove old contents
                      rm -rf *
        
                      # Copy generated DocFX site into gh-pages root
                      cp -R ../docs/_site/* .
        
                      # Ensure GitHub Pages doesn't try to run Jekyll
                      touch .nojekyll
        
                      git add .
        
                      # Commit only if there are changes
                      git commit -m "Update GitHub Pages docs from Jenkins build ${BUILD_NUMBER}" || echo "No changes to commit"
        
                      git push origin gh-pages
                    """
                }
            }
        }

        stage('Cleanup Old Images') {
            steps {
                script {
                    // Keep last 3 numeric tags for IMAGE_BASE, remove older ones
                    sh """
                        docker image ls --format "{{.Repository}}:{{.Tag}} {{.CreatedAt}}" \\
                        | grep '^${params.IMAGE_BASE}:[0-9]' \\
                        | sort -k2 -r \\
                        | tail -n +4 \\
                        | awk '{print \$1}' \\
                        | xargs -r docker rmi
                    """

                    // Remove all test images for this IMAGE_BASE
                    sh """
                        docker image ls --format "{{.Repository}}:{{.Tag}} {{.CreatedAt}}" \\
                        | grep '^${params.IMAGE_BASE}\\.test' \\
                        | awk '{print \$1}' \\
                        | xargs -r docker rmi
                    """

                    // Remove the sonar scan image
                    sh "docker rmi ${params.IMAGE_BASE}.sonarscan || true"

                    // Remove dangling images
                    sh 'docker image prune -f'
                }
            }
        }
    }

    post {
        always {
            sh 'docker ps || true'
        }
        success {
            echo "✅ Build, analysis, docs, and deploy successful. New image tag: ${env.IMAGE_TAG}"
        }
        unstable {
            echo "⚠️ Build completed but marked UNSTABLE due to Quality Gate."
        }
        failure {
            echo "❌ Build or deployment failed."
        }
    }
}
