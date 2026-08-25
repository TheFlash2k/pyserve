(function(){
  const STATE = window.PYSERVE || {};
  const form = document.getElementById('signinForm');
  const username = document.getElementById('username');
  const password = document.getElementById('password');
  const button = document.getElementById('signinBtn');
  const error = document.getElementById('signinError');

  function showError(message){
    error.textContent = message;
    error.classList.add('visible');
  }

  function clearError(){
    error.textContent = '';
    error.classList.remove('visible');
  }

  form.addEventListener('submit', async function(e){
    e.preventDefault();
    clearError();
    const user = username.value.trim();
    const pass = password.value;
    if(!user || !pass){
      showError('Enter a username and a password.');
      return;
    }
    button.disabled = true;
    button.textContent = 'Signing in…';
    let res = null;
    try {
      res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: user, password: pass })
      });
    } catch(err){
      res = null;
    }
    button.disabled = false;
    button.textContent = 'Sign in';
    if(!res){
      showError('Could not reach the server.');
      return;
    }
    if(!res.ok){
      showError(res.status === 401 ? 'Wrong username or password.' : 'Sign in failed.');
      password.value = '';
      password.focus();
      return;
    }
    window.location.replace(STATE.next || '/');
  });
})();
