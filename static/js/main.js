// 创建新文件，添加上传处理逻辑
document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('form');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const progressContainer = document.getElementById('upload-progress');
    
    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(form);
            const xhr = new XMLHttpRequest();
            
            // 显示进度条
            progressContainer.style.display = 'block';
            
            // 设置超时时间为5分钟
            xhr.timeout = 300000;
            
            xhr.upload.addEventListener('progress', function(e) {
                if (e.lengthComputable) {
                    const percentComplete = (e.loaded / e.total) * 100;
                    progressBar.style.width = percentComplete + '%';
                    progressText.textContent = '上传进度: ' + Math.round(percentComplete) + '%';
                }
            });
            
            xhr.addEventListener('load', function() {
                if (xhr.status === 200) {
                    const response = JSON.parse(xhr.responseText);
                    if (response.redirect) {
                        window.location.href = response.redirect;
                    }
                } else {
                    progressText.textContent = '上传失败，请重试';
                }
            });
            
            xhr.addEventListener('timeout', function() {
                progressText.textContent = '上传超时，请尝试分割PDF后再上传';
            });
            
            xhr.addEventListener('error', function() {
                progressText.textContent = '上传出错，请重试';
            });
            
            xhr.open('POST', form.action, true);
            xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
            xhr.send(formData);
        });
    }
}); 