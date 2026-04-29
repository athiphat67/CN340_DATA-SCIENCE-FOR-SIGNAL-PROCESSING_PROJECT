// nav-loader.js
function loadNavbar(activePageId) {
    fetch('navbar.html')
        .then(response => response.text())
        .then(data => {
            document.getElementById('navbar-placeholder').innerHTML = data;
            // ใส่สีทอง (Active) ให้กับหน้าที่กำลังเปิดอยู่
            const activeTab = document.getElementById(activePageId);
            if (activeTab) {
                activeTab.classList.add('active');
            }
        });
}