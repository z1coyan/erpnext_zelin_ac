frappe.listview_settings['My Invoice'] = {
    onload: function (listview) {
		listview.page.clear_primary_action();
        listview.page.add_actions_menu_item(__("取发票号"), ()=>{
            let docnames = listview.get_checked_items(true);
            frappe.call({
					method: "zelin_ac.zelin_accounting.doctype.my_invoice.my_invoice.get_invoice_codes",
					args:{
						docnames: docnames
					},
					freeze: true,
					freeze_message: __("后台处理中，请等待..."),
					callback: function(r) {
					    listview.refresh();
					}
				});
        })
		listview.page.add_inner_button(__("上传发票"), ()=>{
			$('<input type="file" multiple accept=".pdf,.png,.jpg">').on('change', async function() {
				var files = this.files;
				var i = 0;

				async function uploadFile(file) {
					return new Promise(resolve => {
						let reader = new FileReader();

						reader.onload = function(e) {
							var contents = e.target.result;
							//console.log('up_files: ' + file.name);
							frappe.call({
								method: 'zelin_ac.zelin_accounting.doctype.my_invoice.my_invoice.upload_invoices',
								args: {
									filename: file.name,
									filedata: contents
								},
								freeze: true,
								freeze_message: __("请等待上传完成后网页自动刷新..."),
								callback: function(response) {									
									if (response.message && response.message.length){
										frappe.show_alert(__(file.name + '上传成功！'));
										resolve(response.message);
									}

								}
							});
						};

						reader.readAsDataURL(file);
					});
				}

				async function nextFile() {
					if (i >= files.length) {
						listview.refresh();
						return;
					}

					let file = files[i];
					var filename = file.name;
					var totalFileNameLength = 0; // 初始化总字符长度为0
					// 计算总字符长度
					for (var j = 0; j < files.length; j++) {
						var filename = files[j].name;
						totalFileNameLength += filename.length;
					}
					// 检查总字符长度是否超过140个字符
					// if (totalFileNameLength >= 130) {
					// 	frappe.msgprint('所选择的文件名总字符长度超过140个字符，无法上传,请少选择几项。');
					// 	return;
					// }
					// 检查总字符长度是否超过140个字符
					if (files.length >= 30) {
						frappe.msgprint('一次最多允许上传30个文件');
						return;
					}

					if (file.size > 5 * 1024 * 1024) {
						frappe.msgprint(filename + '文件大小超过5MB限制，请对文件处理后再上传。');
						i++;
						nextFile();  // move to next file
						return;
					}

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
		}).addClass("btn-primary");
		// listview.page.add_inner_button(__("获取指定数电发票"), ()=>{
		// 	if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
		// 		navigator.mediaDevices.getUserMedia({ video: true })
		// 			.then(function (stream) {
		// 				var video = document.createElement('video');
		// 				video.srcObject = stream;
		// 				video.play();
		// 				video.addEventListener('click', function () {
		// 					var canvas = document.createElement('canvas');
		// 					canvas.width = video.videoWidth;
		// 					canvas.height = video.videoHeight;
		// 					canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
		// 					var imageUrl = canvas.toDataURL('image/jpeg'); // 获取截取的图片的 Base64 格式
		// 					// 将 imageUrl 发送到服务器或进行其他处理
		// 					console.log('截取的图片:', imageUrl);
		// 					stream.getTracks().forEach(track => track.stop()); // 关闭摄像头
		// 				});
		// 				document.body.appendChild(video);
		// 			})
		// 			.catch(function (error) {
		// 				console.error('获取用户媒体设备失败:', error);
		// 			});
		// 	} else {
		// 		console.error('getUserMedia API 不被此浏览器支持');
		// 	}
		// })

    },
	refresh(listview) {
		listview.page.clear_primary_action();
	}

};