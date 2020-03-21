/*
* File:        jquery.dataTables.rowReordering.js
* Version:     1.0.0.
* Author:      Jovan Popovic 
* 
* Copyright 2012 Jovan Popovic, all rights reserved.
*
* This source file is free software, under either the GPL v2 license or a
* BSD style license, as supplied with this software.
* 
* This source file is distributed in the hope that it will be useful, but 
* WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY 
* or FITNESS FOR A PARTICULAR PURPOSE. 
* 
* Parameters:
* @iIndexColumn     int         Position of the indexing column
* @sURL             String      Server side page tat will be notified that order is changed
* @iGroupingLevel   int         Defines that grouping is used
*/
(function ($) {

    $.fn.rowReordering = function (options) {

        function _fnStartProcessingMode() {
            ///<summary>
            ///Function that starts "Processing" mode i.e. shows "Processing..." dialog while some action is executing(Default function)
            ///</summary>

            if (oTable.fnSettings().oFeatures.bProcessing) {
                $(".dataTables_processing").css('visibility', 'visible');
            }
        }

        function _fnEndProcessingMode() {
            ///<summary>
            ///Function that ends the "Processing" mode and returns the table in the normal state(Default function)
            ///</summary>

            if (oTable.fnSettings().oFeatures.bProcessing) {
                $(".dataTables_processing").css('visibility', 'hidden');
            }
        }

        function fnGetStartPosition(sSelector) {
            var iStart = 1000000;
            $(sSelector, oTable).each(function () {
                iPosition = parseInt(oTable.fnGetData(this, properties.iIndexColumn));
                if (iPosition < iStart)
                    iStart = iPosition;
            });
            return iStart;
        }
		
		function fnCancelSorting(tbody, properties, iLogLevel, sMessage) {
			tbody.sortable('cancel');
			if(iLogLevel<=properties.iLogLevel){
				if(sMessage!= undefined){
					properties.fnAlert(sMessage, "");
				}else{
					properties.fnAlert("Row cannot be moved", "");
				}
			}
			properties.fnEndProcessingMode();
        }

        function fnGetState(sSelector, id) {

            var tr = $("#" + id);
            var iCurrentPosition = oTable.fnGetData(tr[0], properties.iIndexColumn);
            var iNewPosition = -1; // fnGetStartPosition(sSelector);
            var sDirection;
            var trPrevious = tr.prev(sSelector);
            if (trPrevious.length > 0) {
                iNewPosition = parseInt(oTable.fnGetData(trPrevious[0], properties.iIndexColumn));
                if (iNewPosition < iCurrentPosition) {
                    iNewPosition = iNewPosition + 1;
                }
            } else {
                var trNext = tr.next(sSelector);
                if (trNext.length > 0) {
                    iNewPosition = parseInt(oTable.fnGetData(trNext[0], properties.iIndexColumn));
                    if (iNewPosition > iCurrentPosition)//moved back
                        iNewPosition = iNewPosition - 1;
                }
            }
            if (iNewPosition < iCurrentPosition)
                sDirection = "back";
            else
                sDirection = "forward";

            return { sDirection: sDirection, iCurrentPosition: iCurrentPosition, iNewPosition: iNewPosition };

        }

        function fnMoveRows(sSelector, iCurrentPosition, iNewPosition, sDirection, id, sGroup) {
            var iStart = iCurrentPosition;
            var iEnd = iNewPosition;
            if (sDirection == "back") {
                iStart = iNewPosition;
                iEnd = iCurrentPosition;
            }

            $(oTable.fnGetNodes()).each(function () {
                if (sGroup != "" && $(this).attr("data-group") != sGroup)
                    return;
                var tr = this;
                var iRowPosition = parseInt(oTable.fnGetData(tr, properties.iIndexColumn));
                if (iStart <= iRowPosition && iRowPosition <= iEnd) {
                    if (tr.id == id) {
                        oTable.fnUpdate(iNewPosition,
								        oTable.fnGetPosition(tr), // get row position in current model
								        properties.iIndexColumn,
								        false); // false = defer redraw until all row updates are done
                    } else {
                        if (sDirection == "back") {
                            oTable.fnUpdate(iRowPosition + 1,
								        oTable.fnGetPosition(tr), // get row position in current model
								        properties.iIndexColumn,
								        false); // false = defer redraw until all row updates are done
                        } else {
                            oTable.fnUpdate(iRowPosition - 1,
								        oTable.fnGetPosition(tr), // get row position in current model
								        properties.iIndexColumn,
								        false); // false = defer redraw until all row updates are done
                        }
                    }
                }
            });

            var oSettings = oTable.fnSettings();

            //Standing Redraw Extension
            //Author: 	Jonathan Hoguet
            //http://datatables.net/plug-ins/api#fnStandingRedraw
            if (oSettings.oFeatures.bServerSide === false) {
                var before = oSettings._iDisplayStart;
                oSettings.oApi._fnReDraw(oSettings);
                //iDisplayStart has been reset to zero - so lets change it back
                oSettings._iDisplayStart = before;
                oSettings.oApi._fnCalculateEnd(oSettings);
            }
            //draw the 'current' page
            oSettings.oApi._fnDraw(oSettings);
        }

        function _fnAlert(message, type) { alert(message); }

        var oTable = this;

        var defaults = {
            iIndexColumn: 0,
            iStartPosition: 1,
            sURL: null,
            sRequestType: "POST",
            iGroupingLevel: 0,
            fnAlert: _fnAlert,
			iLogLevel: 1,
            sDataGroupAttribute: "data-group",
            fnStartProcessingMode: _fnStartProcessingMode,
            fnEndProcessingMode: _fnEndProcessingMode
        };

        var properties = $.extend(defaults, options);

        var iFrom, iTo;

        return this.each(function () {

            var aaSortingFixed = (oTable.fnSettings().aaSortingFixed == null ? new Array() : oTable.fnSettings().aaSortingFixed);
            aaSortingFixed.push([properties.iIndexColumn, "asc"]);

            oTable.fnSettings().aaSortingFixed = aaSortingFixed;


            for (var i = 0; i < oTable.fnSettings().aoColumns.length; i++) {
                oTable.fnSettings().aoColumns[i].bSortable = false;
                /*for(var j=0; j<aaSortingFixed.length; j++)
                {
                if( i == aaSortingFixed[j][0] )
                oTable.fnSettings().aoColumns[i].bSortable = false;
                }*/
            }
            oTable.fnDraw();

            $("tbody", oTable).sortable({
                cursor: "move",
                update: function (event, ui) {
                    var tbody = $(this);
                    var sSelector = "tbody tr";
                    var sGroup = "";
                    if (properties.bGroupingUsed) {
                        sGroup = $(ui.item).attr(properties.sDataGroupAttribute);
						if(sGroup==null || sGroup==undefined){
							fnCancelSorting(tbody, properties, 3, "Grouping row cannot be moved");
							return;
						}
                        sSelector = "tbody tr[" + properties.sDataGroupAttribute + " ='" + sGroup + "']";
                    }

                    var oState = fnGetState(sSelector, ui.item.context.id);
					if(oState.iNewPosition == -1)
					{
						fnCancelSorting(tbody, properties,2);
						return;
					}

                    if (properties.sURL != null) {
                        properties.fnStartProcessingMode();
                        $.ajax({
                            url: properties.sURL,
                            type: properties.sRequestType,
                            data: { id: ui.item.context.id,
                                fromPosition: oState.iCurrentPosition,
                                toPosition: oState.iNewPosition,
                                direction: oState.sDirection,
                                group: sGroup
                            },
                            success: function () {
                                fnMoveRows(sSelector, oState.iCurrentPosition, oState.iNewPosition, oState.sDirection, ui.item.context.id, sGroup);
                                properties.fnEndProcessingMode();
                            },
                            error: function (jqXHR) {
								fnCancelSorting(tbody, properties, 1, jqXHR.statusText);
                            }
                        });
                    } else {
                        fnMoveRows(sSelector, oState.iCurrentPosition, oState.iNewPosition, oState.sDirection, ui.item.context.id, sGroup);
                    }

                }
            });

        });

    };




})(jQuery);