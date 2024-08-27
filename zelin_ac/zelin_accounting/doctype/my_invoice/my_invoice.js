frappe.ui.form.on("My Invoice", {
    onload: (frm) => {
        if (frm.is_new()) {
           frm.set_value("owner_user", frappe.session.user);
           frm.set_df_property("up_files", "hidden", 1);
    	}
        if (!frm.is_new() && frm.doc.files) {
            frm.set_df_property("up_files", "hidden", 1);
        }
  	},
    refresh: function(frm) {
        frm.$wrapper.find(".menu-btn-group").hide()
        var hasr1 = frappe.user.has_role('System Manager');
        var hasr2 = frappe.user.has_role('Accounts User');
        if(frappe.session.user == "Administrator" || hasr1){
            frm.set_df_property("rep_txt", "hidden", 0);
            frm.set_df_property("rep_txt", "read_only", 0);
        }
        if(hasr1||hasr2){
            frm.set_df_property("invoice_code", "read_only", 0);
            frm.set_df_property("expense_claim", "hidden", 0);
            frm.set_df_property("owner_user", "hidden", 0);
            frm.set_df_property("files", "hidden", 0);
            if (!frm.is_new() && (frm.doc.status=="未使用" || frm.doc.status=="已使用")) {
                frm.add_custom_button(__('取发票号'), () => frm.trigger('get_invoice_code'), __('Actions'));
            }
        }
    },
    net_amount: function(frm) {
        frm.set_value("amount", frm.doc.net_amount + frm.doc.tax);
    },
    tax: function(frm) {
        frm.set_value("amount", frm.doc.net_amount + frm.doc.tax);
    },
    get_invoice_code: (frm) => {
        frappe.call({
            method: 'zelin_ac.zelin_accounting.doctype.my_invoice.my_invoice.get_invoice_code',
            args: {
                docname: frm.docname,
                doctype: frm.doctype,
            },
            callback: function(response) {
                console.log(response.message);
                frm.reload_doc();
            }
        });
	},
    up_files: function(frm) {
        if (frm.is_new()) {
            frappe.msgprint('请先创建单据后再上传附件资料');
            return;
        }

        $('<input type="file" multiple accept=".pdf,.png,.jpg">').on('change', async function() {
            var files = this.files;
            var i = 0;

            async function uploadFile(file) {
                return new Promise(resolve => {
                    let reader = new FileReader();

                    reader.onload = function(e) {
                        var contents = e.target.result;
                        console.log('up_files: ' + file.name);

                        frappe.call({
                            method: 'zelin_ac.zelin_accounting.doctype.my_invoice.my_invoice.upload_file',
                            args: {
                                docname: frm.docname,
                                doctype: frm.doctype,
                                filename: file.name,
                                filedata: contents
                            },
                            callback: function(response) {
                                console.log(response.message);
                                frm.reload_doc();
                                files_source = frm.doc.files
                                frm.set_value("files",files_source);
                                // frm.set_value("files",frm.doc.files);
                                // frm.reload_doc();
                                frappe.show_alert(__(file.name + '上传成功！'));
                                resolve(response.message);
                            }
                        });
                    };
                    reader.readAsDataURL(file);
                });
            }

            async function nextFile() {
                if (i >= files.length) {
                    frm.save();
                    return;
                }

                let file = files[i];

                try {
                    // 等待文件上传完成
                    let uploadResult = await uploadFile(file);
                    i++;
                    nextFile(); // 继续上传下一个文件
                } catch (error) {
                    console.error('File upload failed:', error);
                    i++;
                    nextFile(); // 继续上传下一个文件
                }
            }
            nextFile(); // 开始逐个上传文件
        }).click();
    }
})

