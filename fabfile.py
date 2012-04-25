from fabric.api import cd, env, local, puts, sudo, task
from fabric.contrib import files
from unipath import FSPath as Path

env.hosts = ['ve.djangoproject.com']
env.deploy_base = Path('/home/trac')
env.virtualenv = env.deploy_base.child('venv')
env.code_dir = env.deploy_base.child('code.djangoproject.com')
env.git_url = 'git://github.com/django/code.djangoproject.com.git'
env.default_deploy_ref = 'origin/master'

@task
def deploy():
    """
    Full deploy.
    """
    deploy_trac()
    update_dependencies()
    deploy_trac_media()
    apache("restart")

@task
def deploy_trac(ref=None):
    """
    Update trac-env on the servers from Git.
    """
    ref = ref or env.default_deploy_ref
    puts("Deploying %s" % ref)
    if not files.exists(env.code_dir):
        sudo('git clone %s %s' % (env.git_url, env.code_dir))
    with cd(env.code_dir):
        sudo('git fetch && git reset --hard %s' % ref)

@task
def deploy_trac_media():
    """Deploy Trac media for static serving."""
    sudo('%s/bin/trac-admin %s/trac-env deploy /home/www/trac-media' % (env.virtualenv, env.code_dir))

@task
def apache(cmd):
    """
    Manage the apache service. For example, `fab apache:restart`.
    """
    sudo('invoke-rc.d apache2 %s' % cmd)

@task
def update_dependencies():
    """
    Update dependencies in the virtualenv.
    """
    pip = env.virtualenv.child('bin', 'pip')
    reqs = env.code_dir.child('requirements.txt')
    sudo('%s -q install -U pip' % pip)
    sudo('%s -q install -r %s' % (pip, reqs))

@task
def copy_db():
    """
    Copy the production DB locally for testing.
    """
    local('ssh %s pg_dump -U code.djangoproject -c code.djangoproject | psql code.djangoproject' % env.hosts[0])
