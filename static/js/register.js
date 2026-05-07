document.querySelectorAll('input:not([type="radio"]):not([type="checkbox"]), select, textarea').forEach((el) => {
    el.classList.add('form-control');
});

function getSelectedRoleValue(roleField) {
    if (!roleField) {
        return null;
    }

    if (roleField instanceof RadioNodeList) {
        return roleField.value || null;
    }

    return roleField.value || null;
}

function initRoleCompanyToggle() {
    const form = document.querySelector('form');
    if (!form) {
        return;
    }

    const companyNameInput = form.elements['company_name'] || document.getElementById('id_company_name');
    const roleField = form.elements['role'];

    if (!companyNameInput || !roleField) {
        return;
    }

    const companyContainer = companyNameInput.closest('.col-md-6') || companyNameInput.closest('.mb-2');

    function toggleCompanyNameField() {
        const isCompany = getSelectedRoleValue(roleField) === 'company';

        companyNameInput.disabled = !isCompany;
        companyNameInput.required = isCompany;

        if (!isCompany) {
            companyNameInput.value = '';
        }

        if (companyContainer) {
            companyContainer.style.opacity = isCompany ? '1' : '0.55';
        }
    }

    if (roleField instanceof RadioNodeList) {
        Array.from(roleField).forEach((input) => {
            input.addEventListener('change', toggleCompanyNameField);
        });
    } else {
        roleField.addEventListener('change', toggleCompanyNameField);
    }

    toggleCompanyNameField();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initRoleCompanyToggle);
} else {
    initRoleCompanyToggle();
}