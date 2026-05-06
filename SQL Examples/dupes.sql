IF OBJECT_ID(DROP TABLE if exists #dupes) 

create table #dupes (
	UniqueID varchar(10),
	Activity_Date Date,
	POD varchar(20))

insert into #dupes
values('A1','20190302','CC'),
	  ('A2','20190401','IP'),
	  ('A3','20190412','AE'),
	  ('A3','20190413','AE'),
	  ('A4','20190101','OP'),
	  ('A5','20190502','IP'),
	  ('A5','20190502','IP'),
	  ('A6','20190105','CC'),
	  ('A7','20190303','AE'),
	  ('A8','20190228','IP'),
	  ('A9','20190319','OP'),
	  ('A9','20190319','OP')

	  select distinct * from #dupes
	  select * from #dupes
	  select distinct UniqueID from #dupes
	  select Activity_date, (select distinct uniqueid) from #dupes

	  SELECT UniqueID,
		Count(*) as Volume 
		from #dupes
		group by UniqueID
		having count(*) > 1

		SELECT UniqueID,
			Activity_Date,
			POD,
			Count(*) as Volume 
			from #dupes
			group by UniqueID,
			Activity_Date,
			POD
			having count(*) > 1

	select ROW_NUMBER() OVER(Partition by UniqueID Order by Activity_Date) as RN, *
	from #Dupes




